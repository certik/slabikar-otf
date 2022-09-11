"""
This file creates SVG files for each glyph in the font specified using the
Metafont approach.

The actual shapes are taken from the Slabikář font by Petr Olšák, and the
original metafont source code is copied here for each glyph as a comment for
reference.

The metafont path is represented by nodes, optional tangents and tensions. From
this information one can obtain bezier control points. We implemented the
tangent+tension -> bezier control points calculation exactly. We currently
require all tangents to be specified explicitly. The original Metafont source
has some implicit tangents, so we have estimated those by trial and error by
hand. In the future we could implement the Metafont's algorithm for tangents as
well.

The generated SVG files contain the path of the cursive font. The files are
then processed using Inkscape to produce outlines. We read them in, and convert
to the UFO glif format, which is then used to construct the OTF font.



# Documentation for SVG:
# https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/d#path_commands
#
# One can check the generated svg document at:
# https://validator.w3.org


The otf design units are 1000x1000 pixels EM box.

72 pt = 1 inch
1 em = 11.95517 pt

The metafont design units are 1pt = 0.083645em = 83.6458 px (pixels).

It seems we have roughly 1pt = 40px. Why?
"""

# scale=70 lines up the lowercase letters with Source-Sans
# scale=50 lines up the uppercase letters with Helvetica Neue and most other
# fonts, so it is probably a better option to be consistent.
# scale=40 agress with Metafont's Slabikar
scale = 40
stroke_width = 0.4 * scale


import os
from bezier import compute_control_points
from math import sin, cos, pi
from numpy import array
from glif import Glif, verify, glif2svg, Point

def shift(contour, s):
    p = []
    for x in contour:
        p.append(Point(x=x.x+s[0], y=x.y+s[1], type=x.type, smooth=x.smooth))
    return p

#path = [z1,
#        [left, 1, z1p_tangent, z1p],
#        [z1p_tangent, 1, -sklon2, z0],
#        [-sklon2, 1.5, right, z2],
#        [right, 1.2, -sklon1, z1],
#        [sklon1, 1, sklon1, z3],
#    ]
def _draw(path):
    contour = [
        Point(x=path[0][0], y=path[0][1], type="move", smooth=False)
    ]
    for t1, tension, t2, z in path[1:]:
        if t1 is None:
            contour.append(Point(x=z[0], y=z[1], type="line", smooth=False))
        else:
            z0 = [contour[-1].x, contour[-1].y]
            c1, c2 = compute_control_points(z0, z, t1, t2, tension)
            contour.extend([
                Point(x=c1[0], y=c1[1], type="offcurve", smooth=False),
                Point(x=c2[0], y=c2[1], type="offcurve", smooth=False),
                Point(x=z[0], y=z[1], type="curve", smooth=False),
            ])
    return contour

#path = [(z1,left),1,(z1p,z1p_tangent),1,(z0,-sklon2),1.5,
#        (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1)]
def _draw2(path):
    assert len(path) % 2 == 1
    p2 = [path[0][0]]
    for i in range((len(path)-1)//2):
        node1 = path[2*i]; tension = path[2*i+1]; node2 = path[2*i+2]
        if (len(node2) == 2):
            if tension is None:
                p2.append([None, None, None, node2[0]])
            else:
                p2.append([node1[-1], tension, node2[1], node2[0]])
        else:
            assert len(node2) == 3
            if tension is None:
                p2.append([None, None, None, node2[1]])
            else:
                p2.append([node1[-1], tension, node2[0], node2[1]])
    return _draw(p2)


def create_glif(contours, w, scale):
    for contour in contours:
        for p in contour:
            p.x = float(p.x * scale)
            p.y = float(p.y * scale)
    w = float(w * scale)

    name = "a"
    unicode_hex = None
    anchors = []
    g = Glif(name, unicode_hex, w, contours, anchors)
    verify(g)
    return g

def add_char(charname, width, contours):
    g = create_glif(contours, width, scale)
    f = open(f'letter_{charname}.svg', 'w')
    f.write(glif2svg(g, False, False, stroke_width))
    f.close()

def whatever_y(z0, vec, zy):
    """
    solves the equation z-z0=whatever*vec under the condition of z.y = zy
    """
    w = (zy-z0[1]) / vec[1]
    zx = vec[0] * w + z0[0]
    z = [zx, zy]
    return z

def dir_(angle_deg):
    a = angle_deg * pi/180
    return array([cos(a), sin(a)])

def run(cmd):
    print(cmd)
    r = os.system(cmd)
    if (r != 0):
        raise Exception("Command failed.")

right=array([1,0])
left=array([-1,0])
down=array([0,-1])
up=array([0,1])
# add a curve: first point, and (control-point1, control-point2, node)*n points.
# sklon1:=-(1.5,6); sklon2:=(5,6);
sklon1=-array([1.5,6]); sklon2=array([5,6]);

#def dotah =
#  draw ((0,1){sklon1}..(1,0){right}..{sklon2}(8,6))
#enddef;
dotah = _draw2([((0,1),sklon1),1,((1,0),right),1,((8,6),sklon2)])
eps = stroke_width/2 / scale
z1 = (eps,0); z2 = (0,eps); z3 = (-eps,0); z4=(0,-eps)
dot = _draw2([(z1,up), 1, (z2,left), 1, (z3,down), 1, (z4, right), 1,
    (z1, up)])

#def smycka =
#   draw ((0,7){sklon1}..{sklon1}(-2,0)..{sklon1}(-3.1,-4)..
#       {left}(-5.3,-7)..{-sklon1}(-5.5,-5)..
#       (-2,0)..{sklon2}(5.5,6))
#enddef;
smycka = _draw2([((0,7),sklon1),1,((-2,0),sklon1),1,((-3.1,-4),sklon1),1,
    ((-5.3,-7),left),1,((-5.5,-5),-sklon1),1,
    ((-2,0),(6,5)),1,((5.5,6),sklon2)])

carka = _draw2([((0,9),None),None,((1.5,13),None)])
capcarka = _draw2([((0,15),None),None,((1.5,18),None)])
#def krouzek =
#   draw ((0,9){right}..(0,11){left}..cycle)
#enddef;
eps = 1.0
z1 = (eps,0); z2 = (0,eps); z3 = (-eps,0); z4=(0,-eps)
krouzek = shift(_draw2([(z1,up), 1, (z2,left), 1, (z3,down), 1, (z4, right), 1,
    (z1, up)]), (0, 10))
vokan = _draw2([((0,9),(1,1)),1,((3,11),right),1,((4,9),dir_(-105))])


#def dvetecky (expr a, b) =
#   pickup pencircle scaled (dotkoef*thin);
#   drawdot  (2 + a, 10 + b);
#   drawdot  (4.4 + a, 10 + b);
#   pickup pencircle scaled thin
#enddef;
def dvetecky(x,y):
    #return  [
    #    _draw2([((2+x-0.5,9+y),None),None,((2+1.5+x-0.5,12+y),None)]),
    #    _draw2([((4.4+x-0.5,9+y),None),None,((4.4+1.5+x-0.5,12+y),None)]),
    #]
    return  [
        shift(dot, (2+x,10+y)),
        shift(dot, (4.4+x,10+y)),
    ]


#def hacek =
#  draw ((0,12)..{sklon1}(-.3,10)..{right}(.8,9)..tension2..{sklon2}(5,12))
#enddef;
# Note: (0.2,12) looks better
hacek = _draw2([((0,12),sklon1),1,((-.3,10),sklon1),1,((.8,9),right),2,((5,12),sklon2)])
#def hacekl =
#  draw ((0,12)..{sklon1}(-.3,10)..{right}(.8,9)..tension2..{sklon2}(3.5,12))
#enddef;
hacekl = _draw2([((0,12),sklon1),1,((-.3,10),sklon1),1,((.8,9),right),2,((3.5,12),sklon2)])



# Special characters

# End of the character
#beginchar(1, .7u#, 7u#, 0);  %% pravy konec znaku
#  draw (0,6)..(.7,7);
#endchar;
# Original:
# end_w = 0.7
# New fix:
end_w = sklon2[0]/sklon2[1]  # =5/6=0.833...
add_char("end", end_w, [
    _draw2([((0,6),None), None, ((end_w,7),None)]),
])

# Beginning of the character
#beginchar(2, 5u#, 7u#, 0);  %% levy rovny zacatek znaku
#  draw (0,0)..(5,6);
#endchar;
add_char("begin_straight", 5, [
    _draw2([((0,0),sklon2), 1, ((5,6),sklon2)]),
])

#beginchar(3, 6u#, 7u#, 0);  %% levy prohnuty zacatek znaku
#  draw (0,0){(3,2)}..{sklon2}(6,6);
#endchar;
add_char("begin", 6, [
    _draw2([((0,0),(3,2)), 1, ((6,6),sklon2)]),
])

#beginchar(4, 5u#, 7u#, 0);  %% obecna konvexni spojka za verzalkou a s
#  draw (-4,0){right}..{sklon2}(5,6);
#endchar;
add_char("conn_s", 5, [
    _draw2([((-4,0),right), 1, ((5,6),sklon2)]),
])

#beginchar(5, 7u#, 7u#, 0);  %% delsi konvexni spojka za verzalkou P
#  draw (-4,0){right}..{sklon2}(7,6);
#endchar;
add_char("conn_P", 7, [
    _draw2([((-4,0),right), 1, ((7,6),sklon2)]),
])

#beginchar(6, 3u#, 7u#, 0);  %% kratsi konvexni spojka pro dvojice sv sn
#  draw (-4,0){right}..{sklon2}(3,6);
#endchar;
add_char("conn_sv", 3, [
    _draw2([((-4,0),right), 1, ((3,6),sklon2)]),
])

#beginchar(7, 8u#, 7u#, 0);  %% nabehova carka pro male x
#  draw (0,2){down}..(2,0){right}..tension2..{sklon2}(8,6);
#endchar;
add_char("begin_x", 8, [
    _draw2([((0,2),down), 1, ((2,0),right), 2, ((8,6),sklon2)]),
])


################################################################################

# Character definitions

#beginchar("a", 9.4u#, 7u#, 0);
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
#  z1p=(1.5,6.9);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.2..{-sklon1}z1{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
z1p=(1.5,6.9); z1p_tangent=(-4, -1)
add_char("a", 9.4, [
    _draw2([(z1,left),1,(z1p,z1p_tangent),1,(z0,-sklon2),1.5,
        (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])

#beginchar(adiaeresis, 9.4u#, 7u#, 0); %% \"a
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
#  z1p=(1.5,6.9);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.2..{-sklon1}z1{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#%  dvetecky (0,0); %%% Change 18. 5. 2020 to:
#  dvetecky (-0.5,0);
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
z1p=(1.5,6.9); z1p_tangent=(-4, -1)
add_char("adieresis", 9.4, [
    _draw2([(z1,left),1,(z1p,z1p_tangent),1,(z0,-sklon2),1.5,
        (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))] +
    dvetecky(-0.5,0)
)

#beginchar(aacute, 9.4u#, 13u#, 0);  %% \'a
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
#  z1p=(1.5,6.9);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#  carka shifted (3,0);
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
z1p=(1.5,6.9); z1p_tangent=(-4, -1)
# FIXME: the second tension is 1.5 in aacute in slabikar.mf, a bug
add_char("aacute", 9.4, [
    _draw2([(z1,left),1,(z1p,z1p_tangent),1,(z0,-sklon2),1.5,
        (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(carka, (3,0))
])


#beginchar("b", 9u#, 14u#, 0);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
#  z4=(0,0); z5=(3,7); z6=(9,6);
#  z1p=(4,12); z5p=(2.5,6);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..
#       z3{sklon1}..z4{right}..tension3..z5{left}..z5p{down}..
#       tension2..{sklon2}z6;
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
z4=(0,0); z5=(3,7); z6=(9,6);
z1p=(4,12); z1p_tangent=(3,6); z5p=(2.5,6);
add_char("b", 9, [
    _draw2([(z0,sklon2),1,(z1p,z1p_tangent),1.5,(z1,left),1,(z2,sklon1),1,
        (z3,sklon1),1,(z4,right),3,(z5,left),1,(z5p,down),
        2,(z6,sklon2)]),
])

#beginchar(bnarrow, 7u#, 14u#, 0);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
#  z4=(0,0); z5=(3,7); z6=(7,6);
#  z1p=(4,12); z5p=(2.5,6);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..
#       z3{sklon1}..z4{right}..tension3..z5{left}..z5p{down}..
#       tension2..{sklon2}z6;
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
z4=(0,0); z5=(3,7); z6=(7,6);
z1p=(4,12); z1p_tangent=(3,6); z5p=(2.5,6);
add_char("bnarrow", 7, [
    _draw2([(z0,sklon2),1,(z1p,z1p_tangent),1.5,(z1,left),1,(z2,sklon1),1,
        (z3,sklon1),1,(z4,right),3,(z5,left),1,(z5p,down),
        2,(z6,sklon2)]),
])


#beginchar("c", 8u#, 7u#, 0);
#  z0=(0,6); z1=(1.5,7); z2=(2.5,6); z3=(0,0); z4=(8,6);
#  draw z2..z1{left}..z0{-sklon2}..z3{right}..{sklon2}z4;
#endchar;
z0=(0,6); z1=(1.5,7); z2=(2.5,6); z3=(0,0); z4=(8,6); z2t=(-4,1)
add_char("c", 8, [
    _draw2([(z2,up),1,(z1,left),1,(z0,-sklon2),1,(z3,right),1,(z4,sklon2)])
])

#beginchar(ccaron, 8u#, 12u#, 0);
#  z0=(0,6); z1=(1.5,7); z2=(2.5,6); z3=(0,0); z4=(8,6);
#  draw z2..z1{left}..z0{-sklon2}..z3{right}..{sklon2}z4;
#  hacek shifted (2,0);
#endchar;
z0=(0,6); z1=(1.5,7); z2=(2.5,6); z3=(0,0); z4=(8,6); z2t=(-4,1)
add_char("ccaron", 8, [
    _draw2([(z2,up),1,(z1,left),1,(z0,-sklon2),1,(z3,right),1,(z4,sklon2)]),
    shift(hacek, (2,0))
])

#beginchar("d", 9.4u#, 14u#, 0);
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
#  z1p=(1.5,6.9);
#  z1n-z3 = whatever * (z1-z3); y1n=14;
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1--z1n{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
z1p=(1.5,6.9);z1pt=(-4,-1) # roughly: z0-z1, but adjusted
z1n = whatever_y(z3, array(z1)-array(z3), 14)
add_char("d", 9.4, [
    _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(z1,-sklon1),None,(z1n,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])
add_char("dcaron", 9.4, [
    _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(z1,-sklon1),None,(z1n,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(hacek, (6,2)),
])

#beginchar("e", 5u#, 7u#, 0);
#  z0=(0,6); z1=(-1,7); z2=(-2,5); z3=(-3,1);
#  draw z0{sklon2}..z1{left}..z2{sklon1}..{sklon1}z3;
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(-1,7); z2=(-2,5); z3=(-3,1);
add_char("e", 5, [
    _draw2([(z0,sklon2),1,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])
add_char("eacute", 5, [
    _draw2([(z0,sklon2),1,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(carka, (0,0)),
])
add_char("ecaron", 5, [
    _draw2([(z0,sklon2),1,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(hacek, (-0.5,0)),
])

#beginchar("f", 7u#, 14u#, 7u#);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
#  z1p=(4,12);
#  z3r=(-.8,0); z3l=(-1.6,.3);
#  z4=(-3,-6);  z5=(-2.3,-7);  z6=(7,6);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..z3{sklon1}
#       ..z4{sklon1}..z5{right}..tension3..
#       {(-2,1)}z3r..z3l{down}..z3r{right}..{sklon2}z6;
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
z1p=(4,12);z1p_t=(3,6)
z3r=(-.8,0); z3l=(-1.6,.3);
z4=(-3,-6);  z5=(-2.3,-7);  z6=(7,6);
add_char("f", 7, [
    _draw2([(z0,sklon2),1,(z1p,z1p_t),1.5,(z1,left),1,(z2,sklon1),1,(z3,sklon1),
        1,(z4,sklon1),1,(z5,right),3,(z3r,(-2,1)),1,(z3l,down),1,(z3r,right),1,
            (z6,sklon2)])
])

#beginchar("g", 8.5u#, 7u#, 7u#);
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
#  z1p=(1.5,6.9);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1;
#  smycka shifted (x1,0);
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(1.4,1);
z1p=(1.5,6.9);z1pt=(-4,-1)
add_char("g", 8.5, [
    _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(z1,-sklon1)]),
    shift(smycka, (z1[0],0))
])

#beginchar("h", 9.85u#, 14u#, 0);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
#  z1p=(4,12);
#  z4=(0.15,5);
#  z5n=(x4+2.5,7); z5=(x4+3,6); z6=(x4+1.7,1);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..z3{sklon1};
#  draw z4{-sklon1}..z5n{right}..z5{sklon1}..{sklon1}z6;
#  dotah shifted (x6,0);
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
z1p=(4,12);z1pt=(1,2)
z4=(0.15,5);
z5n=(z4[0]+2.5,7); z5=(z4[0]+3,6); z6=(z4[0]+1.7,1);
add_char("h", 9.85, [
    _draw2([(z0,sklon2),1,(z1p,z1pt),1.5,(z1,left),1,(z2,sklon1),1,
        (z3,sklon1)]),
    _draw2([(z4,-sklon1),1,(z5n,right),1,(z5,sklon1),1,(z6,sklon1)]),
    shift(dotah, (z6[0],0))
])

#beginchar("i", 7u#, 11u#, 0);
#  z0=(0,6); z1=(.5,7); z2=(-1,1); z3-z1=whatever*sklon1; y3=11;
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot z3;
#  pickup pencircle scaled thin;
#  draw z0{sklon2}..{-sklon1}z1{sklon1}..{sklon1}z2;
#  dotah shifted (x2,0);
#endchar;
z0=(0,6); z1=(.5,7); z2=(-1,1); z3 = whatever_y(z1, sklon1, 11)
add_char("i", 7, [
    _draw2([(z0,sklon2),1,(-sklon1,z1,sklon1),1,(z2,sklon1)]),
    shift(dot, z3),
    shift(dotah, (z2[0],0))
])
z3 = whatever_y(z1, sklon1, 9)
add_char("iacute", 7, [
    _draw2([(z0,sklon2),1,(-sklon1,z1,sklon1),1,(z2,sklon1)]),
    shift(dotah, (z2[0],0)),
    shift(carka, (z3[0],0))
])

#beginchar("j", 6u#, 11u#, 7u#);
#  z0=(0,6); z1=(.5,7);
#  z3-z1=whatever*sklon1; y3=11;
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot z3;
#  pickup pencircle scaled thin;
#  draw z0{sklon2}..{-sklon1}z1;
#  smycka shifted (x1,0);
#endchar;
z0=(0,6); z1=(.5,7); z3 = whatever_y(z1, sklon1, 11)
add_char("j", 6, [
    _draw2([(z0,sklon2),1,(z1,-sklon1)]),
    shift(dot, z3),
    shift(smycka, (z1[0],0))
])

#beginchar("k", 10u#, 14u#, 0);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
#  z1p=(4,12);
#  (z4-z3) = whatever*(z2-z3);  y4=5;
#  z5=(2.3,7);  z6=(2,4.5);  z7=(1,y6);  z8=(4,0);  z9=(10,6);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..z3{sklon1};
#  draw z4{-sklon1}..z5{right}..z6..z7{up}..z6..
#  z8{right}..tension3..{sklon2}z9;
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1.2,0);
z1p=(4,12);z1pt=(1,2)
z4 = whatever_y(z3, array(z2)-array(z3), 5)
z5=(2.3,7);  z6=(2,4.5);  z7=(1,z6[1]);  z8=(4,0);  z9=(10,6);
z6t = (-1,-1)
z6t2 = (1,-1)
add_char("k", 10, [
  _draw2([(z0,sklon2),1,(z1p,z1pt),1.5,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
  _draw2([(z4,-sklon1),1,(z5,right),1,(z6,z6t),1,(z7,up),1,(z6,z6t2),1,
      (z8,right),3,(z9,sklon2)]),
])


#beginchar("l", 7u#, 14u#, 0);
#  z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
#  z1p=(4,12);
#  draw z0{sklon2}..z1p..tension1.5..z1{left}..z2{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(4,14); z2=(1.5,10); z3=(-1,1);
z1p=(4,12);z1pt=(1,2)
add_char("l", 7, [
  _draw2([(z0,sklon2),1,(z1p,z1pt),1.5,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
  shift(dotah, (z3[0],0))
])
add_char("lcaron", 7, [
  _draw2([(z0,sklon2),1,(z1p,z1pt),1.5,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
  shift(dotah, (z3[0],0)),
  shift(hacekl, (5.5, 2))
])
add_char("lacute", 7, [
  _draw2([(z0,sklon2),1,(z1p,z1pt),1.5,(z1,left),1,(z2,sklon1),1,(z3,sklon1)]),
  shift(dotah, (z3[0],0)),
  shift(capcarka, (4, 0))
])



#beginchar("m", 15.7u#, 7u#, 0);
#  z0=(0,6); z1=(3,5); z1d=(1.5,0); z2=(6,5); z2d=(4.5,0);
#  z3=(9,5); z4=(7.7,1);
#  z1n=(2.5,7); z2n=(5.5,7); z3n=(8.5,7);
#  draw z0{sklon2}..z1n{right}..z1{sklon1}..{sklon1}z1d;
#  draw z1{-sklon1}..z2n{right}..z2{sklon1}..{sklon1}z2d;
#  draw z2{-sklon1}..z3n{right}..z3{sklon1}..{sklon1}z4;
#  dotah shifted (x4,0);
#endchar;
z0=(0,6); z1=(3,5); z1d=(1.5,0); z2=(6,5); z2d=(4.5,0);
z3=(9,5); z4=(7.7,1);
z1n=(2.5,7); z2n=(5.5,7); z3n=(8.5,7);
add_char("m", 15.7, [
    _draw2([(z0, sklon2),1,(z1n,right),1,(z1,sklon1),1,(z1d,sklon1)]),
    _draw2([(z1,-sklon1),1,(z2n,right),1,(z2,sklon1),1,(z2d,sklon1)]),
    _draw2([(z2,-sklon1),1,(z3n,right),1,(z3,sklon1),1,(z4 ,sklon1)]),
    shift(dotah, (z4[0],0))
])


#beginchar("n", 12.7u#, 7u#, 0);
#  z0=(0,6); z1=(3,5); z1d=(1.5,0); z2=(6,5); z3=(4.7,1);
#  z1n=(2.5,7); z2n=(5.5,7);
#  draw z0{sklon2}..z1n{right}..z1{sklon1}..{sklon1}z1d;
#  draw z1{-sklon1}..z2n{right}..z2{sklon1}..{sklon1}z3;
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(3,5); z1d=(1.5,0); z2=(6,5); z3=(4.7,1);
z1n=(2.5,7); z2n=(5.5,7);
add_char("n", 12.7, [
    _draw2([(z0, sklon2),1,(z1n,right),1,(z1,sklon1),1,(z1d,sklon1)]),
    _draw2([(z1,-sklon1),1,(z2n,right),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])
add_char("ncaron", 12.7, [
    _draw2([(z0, sklon2),1,(z1n,right),1,(z1,sklon1),1,(z1d,sklon1)]),
    _draw2([(z1,-sklon1),1,(z2n,right),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(hacek, (4,0))
])

#beginchar("o", 8u#, 7u#, 0);
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(8,6);
#  z1p=(1.5,6.9); z2p=(2,6);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1{left}..z2p{down}..{sklon2}z3;
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(8,6);
z1p=(1.5,6.9); z2p=(2,6); z1t=(-4,-1)
add_char("o", 8, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
])
add_char("oacute", 8, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(carka, (3,0))
])
add_char("ocircumflex", 8, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(vokan, (0,0))
])

#beginchar(onarrow, 6u#, 7u#, 0);
#  z0=(0,6); z1=(3,7); z2=(-1,0); z3=(6,6);
#  z1p=(1.5,6.9); z2p=(2,6);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1{left}..z2p{down}..{sklon2}z3;
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0); z3=(6,6);
z1p=(1.5,6.9); z2p=(2,6); z1t=(-4,-1)
add_char("onarrow", 6, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
])
add_char("oacutenarrow", 6, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(carka, (3,0))
])
# FIXME: slabikar.mf has otoceny_hacek instead of vokan, a bug
add_char("ocircumflexnarrow", 6, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(vokan, (0,0))
])


#beginchar("p", 10.2u#, 8u#, 7u#);
#  z0=(0,6);
#  z1=(.5,4);  z2n=(3,7); z2=(3.5,6); z3=(2.2,1);
#  z5=(-2.5,-7);
#  (z1-z4)=whatever*(z1-z5); y4=8;
#  draw z0{sklon2}..{-sklon1}z4{sklon1}--z5;
#  draw z1{-sklon1}..z2n{right}..z2{sklon1}..{sklon1}z3;
#  dotah shifted (x3,0);
#endchar;
z0=(0,6);
z1=(.5,4);  z2n=(3,7); z2=(3.5,6); z3=(2.2,1);
z5=(-2.5,-7);
z4 = whatever_y(z1, array(z1)-array(z5), 8)
add_char("p", 10.2, [
    _draw2([(z0, sklon2),1,(-sklon1,z4,sklon1),None,(z5,None)]),
    _draw2([(z1,-sklon1),1,(z2n,right),1,(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])

#beginchar("q", 9u#, 7u#, 7u#);
#  z0=(0,6); z1=(3,7); z2=(-1,0);
#  z1p=(1.5,6.9);
#  z3=(1.1,-.5); z4-z1 = whatever*(z3-z1); y4=-7;
#  z5=(9,6);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.5..{-sklon1}z1{sklon1}..{sklon1}z3..{sklon1}z4;
#  draw z3{-sklon1}..tension2..{sklon2}z5;
#endchar;
z0=(0,6); z1=(3,7); z2=(-1,0);
z1p=(1.5,6.9);z1pt=(-4,-1)
z3=(1.1,-.5); z4 = whatever_y(z1, array(z3)-array(z1), -7)
z5=(9,6);
add_char("q", 9, [
    _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
        (z2,right),1.5,(-sklon1,z1,sklon1),1,(z3,sklon1),1,(z4,sklon1)]),
    _draw2([(z3,-sklon1),2,(z5,sklon2)]),
])

#beginchar("r", 8.4u#, 7u#, 0);
#  z0=(0,6); z1=(.5,7); z2=(2,7); z3=(.4,1);
#  draw z0{sklon2}..{-sklon1}z1{sklon1}..{-sklon1}z2{sklon1}..{sklon1}z3;
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(.5,7); z2=(2,7); z3=(.4,1);
add_char("r", 8.4, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(-sklon1,z2,sklon1),1,
        (z3,sklon1)]),
    shift(dotah, (z3[0],0))
])
add_char("rcaron", 8.4, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(-sklon1,z2,sklon1),1,
        (z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(hacek, (1.4,0))
])
add_char("racute", 8.4, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(-sklon1,z2,sklon1),1,
        (z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(carka, (1.4,0))
])

#beginchar("s", 2u#, 7u#, 0);
#  z0=(0,6); z1=(.5,7); z2=(-.5,1); z3=(-2,0); z4=(-3,2); z5=(7,6);
#  draw z0{sklon2}..{-sklon1}z1{sklon1}..z2{-sklon2}..z3{left}..{(-1,3)}z4;
#endchar;
z0=(0,6); z1=(.5,7); z2=(-.5,1); z3=(-2,0); z4=(-3,2); z5=(7,6);
add_char("s", 2, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
])
add_char("scaron", 2, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
    shift(hacek, (0,0))
])

#beginchar(sleft, 9u#, 7u#, 0);  %% koncove s
#  z0=(0,0); z1=(7.5,7); z2=(6.5,1); z3=(5,0); z4=(3.5,3);
#  draw z0..{sklon2}z1{-sklon2}..z2{-sklon2}..z3{left}..{(-1,3)}z4;
#endchar;
# FIXME: the z0t here seems correct; slabikar.mf is bent, and the end of `s`
# ends up being across the line, which seems like a bug
z0=(0,0); z1=(7.5,7); z2=(6.5,1); z3=(5,0); z4=(3.5,3);
z0t=array(z4)-array(z0)
add_char("sleft", 9, [
    _draw2([(z0, z0t),1,(sklon2,z1,-sklon2),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
])
add_char("scaronleft", 9, [
    _draw2([(z0, z0t),1,(sklon2,z1,-sklon2),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
    shift(hacek, (8,0))
])

#beginchar(sdepth, 2u#, 7u#, 0);
#  z0=(0,6); z1=(.5,7); z2=(-.5,1); z3=(-2,0); z4=(-3.5,2.5); z5=(7,6);
#  draw z0{sklon2}..{-sklon1}z1{sklon1}..z2{-sklon2}..z3{left}..{(-1,3)}z4;
#endchar;
z0=(0,6); z1=(.5,7); z2=(-.5,1); z3=(-2,0); z4=(-3.5,2.5); z5=(7,6);
add_char("sdepth", 2, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
])
add_char("scarondepth", 2, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,-sklon2),1,
        (z3,left), 1, (z4,(-1,3))]),
    shift(hacek, (0,0))
])

#beginchar("t", 9u#, 14u#, 0);
#  z0=(0,6); z1=(4.5,14); z2=(1,0); z3=(9,6);
#  z10=(0,1);
#  draw z0{sklon2}..tension2..{-sklon1}z1--z2{-sklon1}..
#       z10..z2{right}..z3{sklon2};
#endchar;
z0=(0,6); z1=(4.5,14); z2=(1,0); z3=(9,6);
z10=(0,1);z10t=(-5,-6)
add_char("t", 9, [
    _draw2([(z0,sklon2),2,(z1,-sklon1),None,(z2,-sklon1),1,
        (z10,z10t),1,(z2,right),1,(z3,sklon2)])
])
add_char("tcaron", 9, [
    _draw2([(z0,sklon2),2,(z1,-sklon1),None,(z2,-sklon1),1,
        (z10,z10t),1,(z2,right),1,(z3,sklon2)]),
    shift(hacek, (5.5,2))
])

#beginchar("u", 10u#, 7u#, 0);
#  z0=(0,6); z1=(.5,7); z2=(-1,1); z3=(0,0); z4=(3.5,7); z5=(2,1);
#  draw z0{sklon2}..{-sklon1}z1{sklon1}..z2{sklon1}..z3{right}..tension2..
#       {-sklon1}z4{sklon1}..{sklon1}z5;
#  dotah shifted (x5,0);
#endchar;
z0=(0,6); z1=(.5,7); z2=(-1,1); z3=(0,0); z4=(3.5,7); z5=(2,1);
add_char("u", 10, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(-sklon1,z4,sklon1),1,(z5,sklon1)]),
    shift(dotah, (z5[0],0))
])
add_char("uacute", 10, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(-sklon1,z4,sklon1),1,(z5,sklon1)]),
    shift(dotah, (z5[0],0)),
    shift(carka, (2.5,0))
])
add_char("uring", 10, [
    _draw2([(z0, sklon2),1,(-sklon1,z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(-sklon1,z4,sklon1),1,(z5,sklon1)]),
    shift(dotah, (z5[0],0)),
    shift(krouzek, (2.5,0))
])

#beginchar("v", 11u#, 7u#, 0);
#  z0=(0,6); z1=(2.5,6); z11=(2,7);  z2=(1,1);
#  z4=(2,0); z5=(5,7); z6=(11,6);
#  z5p=(4.5,6);
#  draw z0{sklon2}..z11{right}..z1{sklon1}..z2{sklon1}..
#       z4{right}..tension3..z5{left}..z5p{down}..
#       tension2..{sklon2}z6
#endchar;
z0=(0,6); z1=(2.5,6); z11=(2,7);  z2=(1,1);
z4=(2,0); z5=(5,7); z6=(11,6);
z5p=(4.5,6);
add_char("v", 11, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z4,right),3,(z5,left),1,(z5p,down),2,(z6,sklon2)])
])

#beginchar(vnarrow, 9u#, 7u#, 0);
#  z0=(0,6); z1=(2.5,6); z11=(2,7);  z2=(1,1);
#  z4=(2,0); z5=(5,7); z6=(9,6);
#  z5p=(4.5,6);
#  draw z0{sklon2}..z11{right}..z1{sklon1}..z2{sklon1}..
#       z4{right}..tension3..z5{left}..z5p{down}..
#       tension2..{sklon2}z6
#endchar;
z0=(0,6); z1=(2.5,6); z11=(2,7);  z2=(1,1);
z4=(2,0); z5=(5,7); z6=(9,6);
z5p=(4.5,6);
add_char("vnarrow", 9, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z4,right),3,(z5,left),1,(z5p,down),2,(z6,sklon2)])
])


#beginchar("w", 14u#, 7u#, 0);
#  z0=(0,6); z1=(2.5,6); z11=(2,7);
#  z2=(1,1); z3=(2,0); z4=(5.5,7);
#  z5=(4,1); z6=(5,0); z7=(8,7); z8=(14,6);
#  z7p=(7.5,6);
#  draw z0{sklon2}..z11{right}..z1{sklon1}..z2{sklon1}..
#       z3{right}..tension2..{-sklon1}z4{sklon1}..
#       z5{sklon1}..z6{right}..tension3..z7{left}..z7p{down}..
#       tension2..{sklon2}z8
#endchar;
z0=(0,6); z1=(2.5,6); z11=(2,7);
z2=(1,1); z3=(2,0); z4=(5.5,7);
z5=(4,1); z6=(5,0); z7=(8,7); z8=(14,6);
z7p=(7.5,6);
add_char("w", 14, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(-sklon1,z4,sklon1),1,
        (z5,sklon1),1,(z6,right),3,(z7,left),1,(z7p,down),2,(z8,sklon2)])
])

#beginchar(wnarrow, 12u#, 7u#, 0);
#  z0=(0,6); z1=(2.5,6); z11=(2,7);
#  z2=(1,1); z3=(2,0); z4=(5.5,7);
#  z5=(4,1); z6=(5,0); z7=(8,7); z8=(12,6);
#  z7p=(7.5,6);
#  draw z0{sklon2}..z11{right}..z1{sklon1}..z2{sklon1}..
#       z3{right}..tension2..{-sklon1}z4{sklon1}..
#       z5{sklon1}..z6{right}..tension3..z7{left}..z7p{down}..
#       tension2..{sklon2}z8
#endchar;
z0=(0,6); z1=(2.5,6); z11=(2,7);
z2=(1,1); z3=(2,0); z4=(5.5,7);
z5=(4,1); z6=(5,0); z7=(8,7); z8=(12,6);
z7p=(7.5,6);
add_char("wnarrow", 12, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(-sklon1,z4,sklon1),1,
        (z5,sklon1),1,(z6,right),3,(z7,left),1,(z7p,down),2,(z8,sklon2)])
])


#beginchar("x", 5u#, 7u#, 0);
#  z0=(0,6); z1=(1,7);
#  z2=(-1.5,7);  z3=(-3,1);
#  draw z0{sklon2}..z1;
#  draw z2{sklon1}..{sklon1}z3;
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(1,7);
z2=(-1.5,7);  z3=(-3,1);
add_char("x", 5, [
    _draw2([(z0,sklon2),1,(z1,sklon2)]),
    _draw2([(z2,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])

#beginchar("y", 11u#, 7u#, 7u#);
#  z0=(0,6); z1=(2.5,6); z11=(2,7);
#  z2=(1,1); z3=(2,0); z4=(5.5,7);
#  draw z0{sklon2}..z11{right}..z1{sklon1}..z2{sklon1}..
#       z3{right}..tension2..{-sklon1}z4;
#  smycka shifted (x4,0);
#endchar;
z0=(0,6); z1=(2.5,6); z11=(2,7);
z2=(1,1); z3=(2,0); z4=(5.5,7);
add_char("y", 11, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(z4,-sklon1)]),
    shift(smycka, (z4[0],0))
])
add_char("yacute", 11, [
    _draw2([(z0,sklon2),1,(z11,right),1,(z1,sklon1),1,(z2,sklon1),1,
        (z3,right),2,(z4,-sklon1)]),
    shift(smycka, (z4[0],0)),
    shift(carka, (4.5,0))
])


#beginchar("z", 11u#, 7u#, 0);
#  z0=(0,6); z1=(1.5,7); z2=(4,7); z3=(1,0);
#  z4=(4,0); z5=(11,6);
#  draw z0{sklon2}..z1{right}..{-sklon1}z2{sklon1}..
#       {sklon1}z3{-sklon1}..z4{right}..tension1.5..{sklon2}z5;
#endchar;
z0=(0,6); z1=(1.5,7); z2=(4,7); z3=(1,0);
z4=(4,0); z5=(11,6);
add_char("z", 11, [
    _draw2([(z0,sklon2),1,(z1,right),1,(-sklon1,z2,sklon1),1,
        (sklon1,z3,-sklon1),1,(z4,right),1.5,(z5,sklon2)]),
])
add_char("zcaron", 11, [
    _draw2([(z0,sklon2),1,(z1,right),1,(-sklon1,z2,sklon1),1,
        (sklon1,z3,-sklon1),1,(z4,right),1.5,(z5,sklon2)]),
    shift(hacek, (2.5,0))
])

################################################################################
# Uppercase

#beginchar("A", 11.4u#, 14u#, 0);
#  z0=(0,6); z1=(7,14); z2=(1,0); z3=(3.4,1);
#  z1p=(6,13.9);
#  draw z1{left}..z1p..z0{sklon1}..
#       z2{right}..tension2.5..{-sklon1}z1{sklon1}..z3{sklon1};
#  dotah shifted (x3,0);
#endchar;
z0=(0,6); z1=(7,14); z2=(1,0); z3=(3.4,1);
z1p=(6,13.9);z1t=(-4,-1)
add_char("A_", 11.4, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,sklon1),1,
        (z2,right),2.5,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))
])
add_char("A_acute", 11.4, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,sklon1),1,
        (z2,right),2.5,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0)),
    shift(capcarka, (6,0))
])
add_char("A_dieresis", 11.4, [
    _draw2([(z1,left),1,(z1p,z1t),1,(z0,sklon1),1,
        (z2,right),2.5,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
    shift(dotah, (z3[0],0))] +
    dvetecky(3,6)
)

#beginchar("B", 9u#, 14u#, 0);
#  z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
#  z3=(0,4);  z4=(6,8);  z4l=(x4-1,y4);
#  z5=(8.5,4);  z6=(5,0);  z7=(3.5,2);
#  draw z1{left}..z2p{sklon1}..z2{left}..z0{-sklon1}..
#      z1{right}..{dir190}z4..z4l{up}..z4{dir-20}..z5{sklon1}..z6{left}..z7;
#endchar;
z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
z3=(0,4);  z4=(6,8);  z4l=(z4[0]-1,z4[1]);
z5=(8.5,4);  z6=(5,0);  z7=(3.5,2); z7t=(1,2)
add_char("B_", 9, [
    _draw2([(z1,left),1,(z2p,sklon1),1,(z2,left),1,(z0,-sklon1),1,
        (z1,right),1,(z4,dir_(190)),1,(z4l,up),1,(z4,dir_(-20)),1,(z5,sklon1),
        1,(z6,left),1,(z7,z7t)])
])

#beginchar("C", 9.5u#, 14u#, 0);
#  z0=(0,6);  z1=(5,12.5);  z2=(x1+.3,11);  z3=(x1+.1,14);
#  z4=(1.5,0);  z5=(x4+8,6);
#  draw z1{sklon1}..z2{right}..tension1.5..z3{left}..tension2..
#       z0{sklon1}..z4{right}..tension1.5..{sklon2}z5;
#endchar;
z0=(0,6);  z1=(5,12.5);  z2=(z1[0]+.3,11);  z3=(z1[0]+.1,14);
z4=(1.5,0);  z5=(z4[0]+8,6);
add_char("C_", 9.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z0,sklon1),1,(z4,right),1.5,(z5,sklon2)])
])
add_char("C_caron", 9.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z0,sklon1),1,(z4,right),1.5,(z5,sklon2)]),
    shift(hacek, (5,6))
])

#beginchar("D", 8u#, 14u#, 0);
#  z1=(9,14);  z2=(3,3);  z3=(1,0);  z4=(.5,0); z4n=(x4,1);
#  z5=(4,0); z6=(7,4);  z7=(6,14);  z8=(3.5,13);  z9=(3.5,9);
#  z10=(5.5,12);
#  draw z1{-sklon2}..z2{sklon1}..z3..z4{left}..z4n{right}..
#       z5{right}..z6{-sklon1}..z7{left}..
#       z8{-sklon2}..z9{right}..{-sklon1}z10;
#endchar;
z1=(9,14);  z2=(3,3);  z3=(1,0);  z4=(.5,0); z4n=(z4[0],1);
z5=(4,0); z6=(7,4);  z7=(6,14);  z8=(3.5,13);  z9=(3.5,9);
z10=(5.5,12);
z3t=(-4,-1)
add_char("D_", 8, [
    _draw2([(z1,-sklon2),1,(z2,sklon1),1,(z3,z3t),1,(z4,left),1,(z4n,right),1,
        (z5,right),1,(z6,-sklon1),1,(z7,left),1,
        (z8,-sklon2),1,(z9,right),1,(z10,-sklon1)]),
])
add_char("D_caron", 8, [
    _draw2([(z1,-sklon2),1,(z2,sklon1),1,(z3,z3t),1,(z4,left),1,(z4n,right),1,
        (z5,right),1,(z6,-sklon1),1,(z7,left),1,
        (z8,-sklon2),1,(z9,right),1,(z10,-sklon1)]),
    shift(hacek, (7,6))
])

#beginchar("E", 9.5u#, 14u#, 0);
#  z0=(0,6);  z1=(4,12.5);  z2=(x1+.3,11);  z3=(x1+.1,14);
#  z6=(2,8.5);  z6n=(x6+1,y6);
#  z4=(1.5,0);  z5=(x4+8,6);
#  draw z1{sklon1}..z2{right}..tension1.5..z3{left}..tension2..
#       z6..z6n{up}..z6..
#       z0..tension1.5and1..z4{right}..tension1.5..{sklon2}z5;
#endchar;
z0=(0,6);  z1=(4,12.5);  z2=(z1[0]+.3,11);  z3=(z1[0]+.1,14);
z6=(2,8.5);  z6n=(z6[0]+1,z6[1]);
z4=(1.5,0);  z5=(z4[0]+8,6);
z6t=(1,-3); z6t2=(-1,-1); z0t=(-4,-7)
add_char("E_", 9.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z6,z6t),1,(z6n,up),1,(z6,z6t2),1,
        (z0,z0t),1.3,(z4,right),1.5,(z5,sklon2)]),
])
add_char("E_acute", 9.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z6,z6t),1,(z6n,up),1,(z6,z6t2),1,
        (z0,z0t),1.3,(z4,right),1.5,(z5,sklon2)]),
    shift(capcarka, (5,0))
])
add_char("E_caron", 9.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z6,z6t),1,(z6n,up),1,(z6,z6t2),1,
        (z0,z0t),1.3,(z4,right),1.5,(z5,sklon2)]),
    shift(hacek, (4.5,6))
])

#beginchar("F", 5u#, 14u#, 0);  charic := 7u#;
#   z1=(4,12.5);  z2=(3,10);  z3=(2.3,12.5);  z4=(4,14);
#   z5=(7,13.5);  z6=(12,14);
#   z7=(4,4);  z8=(1,0);  z9=(0,3);
#   z10=(2,7);  z11=(6,9);  z12=(6.5,7);
#   draw z1{sklon1}..z2..z3{-sklon1}..z4{right}..z5..{right}z6;
#   draw z5{-sklon2}..z7{sklon1}..z8{left}..{-sklon1}z9;
#   draw z10..z11{right}..{sklon1}z12;
#endchar;
z1=(4,12.5);  z2=(3,10);  z3=(2.3,12.5);  z4=(4,14);
z5=(7,13.5);  z6=(12,14);
z7=(4,4);  z8=(1,0);  z9=(0,3);
z10=(2,7);  z11=(6,9);  z12=(6.5,7);
z2t=(-1,0); z5t=(4,-1); z10t=(1,1)
add_char("F_", 5, [
    _draw2([(z1,sklon1),1,(z2,z2t),1,(z3,-sklon1),1,(z4,right),1,(z5,z5t),1,
            (z6,right)]),
    _draw2([(z5,-sklon2),1,(z7,sklon1),1,(z8,left),1,(z9,-sklon1)]),
    _draw2([(z10,z10t),1,(z11,right),1,(z12,sklon1)])
])

#beginchar("G", 10.5u#, 14u#, 7u#);
#  z0=(0,6);  z1=(5,12.5);  z2=(x1+.3,11);  z3=(x1+.1,14);
#  z4=(1,0);  z5=(x4+4,7);
#  draw z1{sklon1}..z2{right}..tension1.5..z3{left}..tension2..
#       z0{sklon1}..z4{right}..tension1.5..{-sklon1}z5;
#  smycka shifted (x5,0);
#endchar;
z0=(0,6);  z1=(5,12.5);  z2=(z1[0]+.3,11);  z3=(z1[0]+.1,14);
z4=(1,0);  z5=(z4[0]+4,7);
add_char("G_", 10.5, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z0,sklon1),1,(z4,right),1.5,(z5,-sklon1)]),
    shift(smycka, (z5[0],0))
])

#beginchar("H", 13u#, 14u#, 0);
#  z1=(1.5,11);  z2=(4.5,14);  z3=(5,12);  z4=(2,1);
#  z5=(1,0);  z6=(0.5,3);  z7=(6,8);
#  z8=(9.5,11.5);  z9=(9,14);  z10=(8,13);  z11=(5,1);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{left}..z6{-sklon1}..tension1.5..z7..z8{-sklon1}..
#       z9{left}..z10{sklon1}..{sklon1}z11;
#  dotah shifted (x11,0);
#endchar;
z1=(1.5,11);  z2=(4.5,14);  z3=(5,12);  z4=(2,1);
z5=(1,0);  z6=(0.5,3);  z7=(6,8);
z8=(9.5,11.5);  z9=(9,14);  z10=(8,13);  z11=(5,1);
z7t=(1,1)
add_char("H_", 13, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,left),1,(z6,-sklon1),1.5,(z7,z7t),1,(z8,-sklon1),1,
        (z9,left),1,(z10,sklon1),1,(z11,sklon1)]),
    shift(dotah, (z11[0],0))
])

#beginchar("I", 5u#, 14u#, 0);
#  z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(3.2,2);
#  z5=(1,0);  z6=(-.5,3);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{left}..{up}z6;
#endchar;
z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(3.2,2);
z5=(1,0);  z6=(-.5,3);
add_char("I_", 5, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,left),1,(z6,up)]),
])
add_char("I_acute", 5, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,left),1,(z6,up)]),
    shift(capcarka, (6,0))
])

#beginchar("J", 10.1u#, 14u#, 7u#);
#  z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(4.6,7);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4;
#  smycka shifted (x4,0);
#endchar;
z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(4.6,7);
add_char("J_", 10.1, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1)]),
    shift(smycka, (z4[0],0))
])

#beginchar("K", 15u#, 14u#, 0);
#  z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(3.2,2);
#  z5=(1,0);  z6=(-.5,3);
#  z7=(12,11);  z8=(10,14);  z9=(5,8);  z9p=(x9+1,y9);
#  z10=(9,0);  z11=(15,6);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{left}..{up}z6;
#  draw z7{dir110}..z8{left}..tension2..
#       z9p{dir215}..z9{up}..z9p{dir-35}..
#       tension1.5..z10{right}..tension3..{sklon2}z11;
#endchar;
z1=(2.5,11);  z2=(5.5,14);  z3=(6,12);  z4=(3.2,2);
z5=(1,0);  z6=(-.5,3);
z7=(12,11);  z8=(10,14);  z9=(5,8);  z9p=(z9[0]+1,z9[1]);
z10=(9,0);  z11=(15,6);
add_char("K_", 15, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,left),1,(z6,up)]),
    _draw2([(z7,dir_(110)),1,(z8,left),2,(z9p,dir_(215)),1,(z9,up),1,
        (z9p,dir_(-35)),1.5,(z10,right),3,(z11,sklon2)]),
])

#beginchar("L", 12u#, 14u#, 0);
#  z1=(4,14);  z2=(6,9);  z3=(9,14);  z4=(7,12);
#  z5=(2,1);  z5d=(.5,0);  z5p=(-.5,.8);  z6=(6,0);  z7=(12,6);
#  draw z1..z2{right}..tension1.7..z3{left}..z4{sklon1}..
#       z5..z5d{left}..z5p{up}..z5..z6{right}..tension2..{sklon2}z7;
#endchar;
z1=(4,14);  z2=(6,9);  z3=(9,14);  z4=(7,12);
z5=(2,1);  z5d=(.5,0);  z5p=(-.5,.8);  z6=(6,0);  z7=(12,6);
z1t=(-1,-1); z5t=(-3,-4); z5t2=(8,-5)
add_char("L_", 12, [
    _draw2([(z1,z1t),1,(z2,right),1.7,(z3,left),1,(z4,sklon1),1,
        (z5,z5t),1,(z5d,left),1,(z5p,up),1,(z5,z5t2),1,(z6,right),2,
            (z7,sklon2)]),
])
add_char("L_acute", 12, [
    _draw2([(z1,z1t),1,(z2,right),1.7,(z3,left),1,(z4,sklon1),1,
        (z5,z5t),1,(z5d,left),1,(z5p,up),1,(z5,z5t2),1,(z6,right),2,
            (z7,sklon2)]),
    shift(capcarka, (7,0))
])
add_char("L_caron", 12, [
    _draw2([(z1,z1t),1,(z2,right),1.7,(z3,left),1,(z4,sklon1),1,
        (z5,z5t),1,(z5d,left),1,(z5p,up),1,(z5,z5t2),1,(z6,right),2,
            (z7,sklon2)]),
    shift(hacek, (6,6))
])

#beginchar("M", 15u#, 14u#, 0);
#  z1=(0.5,11);  z2=(3.5,14);  z3=(4,12);  z4=(0.8,0);
#                z5=(6.5,14);  z6=(7,12);  z7=(3.8,0);
#                z8=(9.5,14);  z9=(10,12);  z10=(7,1);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4;
#  draw z3{-sklon1}..tension1.5..z5{right}..z6{sklon1}..{sklon1}z7;
#  draw z6{-sklon1}..tension1.5..z8{right}..z9{sklon1}..{sklon1}z10;
#  dotah shifted (x10,0);
#endchar;
z1=(0.5,11);  z2=(3.5,14);  z3=(4,12);  z4=(0.8,0);
z5=(6.5,14);  z6=(7,12);  z7=(3.8,0);
z8=(9.5,14);  z9=(10,12);  z10=(7,1);
add_char("M_", 15, [
    _draw2([(z1, sklon2),1  ,(z2,right),1,(z3,sklon1),1,(z4,sklon1)]),
    _draw2([(z3,-sklon1),1.5,(z5,right),1,(z6,sklon1),1,(z7,sklon1)]),
    _draw2([(z6,-sklon1),1.5,(z8,right),1,(z9,sklon1),1,(z10,sklon1)]),
    shift(dotah, (z10[0],0))
])

#beginchar("N", 12u#, 14u#, 0);
#  z1=(0.5,11);  z2=(3.5,14);  z3=(4,12);  z4=(0.8,0);
#                z5=(6.5,14);  z6=(7,12);  z7=(4,1);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4;
#  draw z3{-sklon1}..tension1.5..z5{right}..z6{sklon1}..{sklon1}z7;
#  dotah shifted (x7,0);
#endchar;
z1=(0.5,11);  z2=(3.5,14);  z3=(4,12);  z4=(0.8,0);
z5=(6.5,14);  z6=(7,12);  z7=(4,1);
add_char("N_", 12, [
    _draw2([(z1, sklon2),1  ,(z2,right),1,(z3,sklon1),1,(z4,sklon1)]),
    _draw2([(z3,-sklon1),1.5,(z5,right),1,(z6,sklon1),1,(z7,sklon1)]),
    shift(dotah, (z7[0],0))
])
add_char("N_caron", 12, [
    _draw2([(z1, sklon2),1  ,(z2,right),1,(z3,sklon1),1,(z4,sklon1)]),
    _draw2([(z3,-sklon1),1.5,(z5,right),1,(z6,sklon1),1,(z7,sklon1)]),
    shift(dotah, (z7[0],0)),
    shift(hacek, (5,7))
])

#beginchar("O", 5u#, 14u#, 0);  charic := 2u#;
#  z0=(0,6); z1=(6,14); z2=(1,0); z3=(10,14);
#  z1p=(4.5,13.9); z2p=(5.5,13);  z1d=(6.5,13);
#  draw z1{left}..z1p..tension1.5and1..z0{sklon1}..tension1.5..
#       z2{right}..tension2..z1d..z1{left}..z2p{down}..{sklon2}z3;
#endchar;
z0=(0,6); z1=(6,14); z2=(1,0); z3=(10,14);
z1p=(4.5,13.9); z2p=(5.5,13);  z1d=(6.5,13);
z1pt=(-3,-1); z1dt=(0,1)
add_char("O_", 5, [
    _draw2([(z1,left),1,(z1p,z1pt),1.25,(z0,sklon1),1.5,
        (z2,right),2,(z1d,z1dt),1,(z1,left),1,(z2p,down),1,(z3,sklon2)]),
])
add_char("O_acute", 5, [
    _draw2([(z1,left),1,(z1p,z1pt),1.25,(z0,sklon1),1.5,
        (z2,right),2,(z1d,z1dt),1,(z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(capcarka, (6,0))
])
add_char("O_circumflex", 5, [
    _draw2([(z1,left),1,(z1p,z1pt),1.25,(z0,sklon1),1.5,
        (z2,right),2,(z1d,z1dt),1,(z1,left),1,(z2p,down),1,(z3,sklon2)]),
    shift(vokan, (3.6,7))
])

#beginchar("P", 4u#, 14u#, 0);   charic := 5u#;
#  z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
#  z3=(0,4);  z4=(5,8);
#  draw z1{left}..z2p{sklon1}..z2{left}..z0{-sklon1}..
#      z1{right}..{left}z4;
#endchar;
z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
z3=(0,4);  z4=(5,8);
add_char("P_", 4, [
    _draw2([(z1,left),1,(z2p,sklon1),1,(z2,left),1,(z0,-sklon1),1,
        (z1,right),1,(z4,left)]),
])

#beginchar("Q", 10.9u#, 14u#, 7u#);
#  z0=(0,6);  z1=(5,12.5);  z2=(x1+.3,11);  z3=(x1+.1,14);
#  z4=(1,0);  z5=(5,7);
#  z6=(3,-.5);  z7-z6 = whatever*(z5-z6);  y7=-7;
#  z8=(x6+7.9,6);
#  draw z1{sklon1}..z2{right}..tension1.5..z3{left}..tension2..
#       z0{sklon1}..z4{right}..tension1.5..
#       {-sklon1}z5{sklon1}..z6{sklon1}..{sklon1}z7;
#  draw z6{-sklon1}..tension2..{sklon2}z8;
#endchar;
z0=(0,6);  z1=(5,12.5);  z2=(z1[0]+.3,11);  z3=(z1[0]+.1,14);
z4=(1,0);  z5=(5,7);
z6=(3,-.5);  z7 = whatever_y(z6, array(z5)-array(z6), -7);
z8=(z6[0]+7.9,6);
add_char("Q_", 10.9, [
    _draw2([(z1,sklon1),1,(z2,right),1.5,(z3,left),2,
        (z0,sklon1),1,(z4,right),1.5,
        (-sklon1,z5,sklon1),1,(z6,sklon1),1,(z7,sklon1)]),
    _draw2([(z6,-sklon1),2,(z8,sklon2)])
])

#beginchar("R", 14u#, 14u#, 0);
#  z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
#  z3=(0,4);  z4=(6,8);  z4l=(x4-1,y4);
#  z10=(8,0);  z11=(14,6);
#  draw z1{left}..z2p{sklon1}..z2{left}..z0{-sklon1}..
#      z1{right}..{dir215}z4..z4l{up}..z4{dir-35}..
#       tension1.5..z10{right}..tension3..{sklon2}z11;
#endchar;
z0=(0,6);  z1=(8,14);  z2=(1,0);  z2p=(3,3);
z3=(0,4);  z4=(6,8);  z4l=(z4[0]-1,z4[1]);
z10=(8,0);  z11=(14,6);
add_char("R_", 14, [
    _draw2([(z1,left),1,(z2p,sklon1),1,(z2,left),1,(z0,-sklon1),1,
        (z1,right),1,(z4,dir_(215)),1,(z4l,up),1,(z4,dir_(-35)),
        1.5,(z10,right),3,(z11,sklon2)]),
])
add_char("R_caron", 14, [
    _draw2([(z1,left),1,(z2p,sklon1),1,(z2,left),1,(z0,-sklon1),1,
        (z1,right),1,(z4,dir_(215)),1,(z4l,up),1,(z4,dir_(-35)),
        1.5,(z10,right),3,(z11,sklon2)]),
    shift(hacek, (7,6))
])
add_char("R_acute", 14, [
    _draw2([(z1,left),1,(z2p,sklon1),1,(z2,left),1,(z0,-sklon1),1,
        (z1,right),1,(z4,dir_(215)),1,(z4l,up),1,(z4,dir_(-35)),
        1.5,(z10,right),3,(z11,sklon2)]),
    shift(capcarka, (8,0))
])

#beginchar("S", 6u#, 14u#, 0);   charic := 3u#;
#  z1=(4,14);  z2=(6,9);  z3=(9,14);  z4=(7,12);
#  z5=(4.2,2);  z6=(x5-2.2,0); z7=(x6-1.5,3);
#  draw z1..z2{right}..tension1.7..z3{left}..z4{sklon1}..{sklon1}z5..
#       z6{left}..{up}z7;
#endchar;
z1=(4,14);  z2=(6,9);  z3=(9,14);  z4=(7,12);
z5=(4.2,2);  z6=(z5[0]-2.2,0); z7=(z6[0]-1.5,3);
z1t=(-1,-1)
add_char("S_", 6, [
    _draw2([(z1,z1t),1,(z2,right),1.7,(z3,left),1,(z4,sklon1),1,(z5,sklon1),1,
        (z6,left),1,(z7,up)]),
])
add_char("S_caron", 6, [
    _draw2([(z1,z1t),1,(z2,right),1.7,(z3,left),1,(z4,sklon1),1,(z5,sklon1),1,
        (z6,left),1,(z7,up)]),
    shift(hacek, (7,6))
])

#beginchar("T", 5u#, 14u#, 0);   charic := 7u#;
#   z1=(4,12.5);  z2=(3,10);  z3=(2.3,12.5);  z4=(4,14);
#   z5=(7,13.5);  z6=(12,14);
#   z7=(4,4);  z8=(1,0);  z9=(0,3);
#   draw z1{sklon1}..z2..z3{-sklon1}..z4{right}..z5..{right}z6;
#   draw z5{-sklon2}..z7{sklon1}..z8{left}..{-sklon1}z9;
#endchar;
z1=(4,12.5);  z2=(3,10);  z3=(2.3,12.5);  z4=(4,14);
z5=(7,13.5);  z6=(12,14);
z7=(4,4);  z8=(1,0);  z9=(0,3);
z2t=(-1,0); z5t=(4,-1);
add_char("T_", 5, [
    _draw2([(z1,sklon1),1,(z2,z2t),1,(z3,-sklon1),1,(z4,right),1,(z5,z5t),1,
            (z6,right)]),
    _draw2([(z5,-sklon2),1,(z7,sklon1),1,(z8,left),1,(z9,-sklon1)])
])
add_char("T_caron", 5, [
    _draw2([(z1,sklon1),1,(z2,z2t),1,(z3,-sklon1),1,(z4,right),1,(z5,z5t),1,
            (z6,right)]),
    _draw2([(z5,-sklon2),1,(z7,sklon1),1,(z8,left),1,(z9,-sklon1)]),
    shift(hacek, (7,6))
])

#beginchar("U", 11.7u#, 14u#, 0);
#  z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
#  z5=(0.5,0);  z6=(7,14);  z7=(3.7,1);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{right}..tension1.7..{-sklon1}z6--z7;
#  dotah shifted (x7,0);
#endchar;
z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
z5=(0.5,0);  z6=(7,14);  z7=(3.7,1);
add_char("U_", 11.7, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z6,-sklon1),None,(z7,None)]),
    shift(dotah, (z7[0],0))
])
add_char("U_acute", 11.7, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z6,-sklon1),None,(z7,None)]),
    shift(dotah, (z7[0],0)),
    shift(capcarka, (5.5,0))
])
add_char("U_ring", 11.7, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z6,-sklon1),None,(z7,None)]),
    shift(dotah, (z7[0],0)),
    shift(krouzek, (5.5,6))
])

#beginchar("V", 5.5u#, 14u#, 0);  charic := 5u#;
#  z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
#  z5=(0.5,0);  z9=(6.5,14);  z9d=(x9+.5,y9-1);  z9p=(x9-.5,y9-1);
#  z10=(10.5,14);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{right}..tension1.7..{-sklon1}z9d..
#       z9{left}..z9p{down}..{sklon2}z10;
#endchar;
z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
z5=(0.5,0);  z9=(6.5,14);  z9d=(z9[0]+.5,z9[1]-1);  z9p=(z9[0]-.5,z9[1]-1);
z10=(10.5,14);
add_char("V_", 5.5, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z9d,-sklon1),1,
        (z9,left),1,(z9p,down),1,(z10,sklon2)]),
])

#beginchar("W", 8.3u#, 14u#, 0);  charic := 5u#;
#  z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);
#  z4=(0,1);    z5=(0.5,0);    z6=(7,14);
#  z7=(3.8,1);  z8=(4.3,0);
#  z9=(10.3,14);  z9d=(x9+.5,y9-1);  z9p=(x9-.5,y9-1);
#  z10=(14.7,14);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{right}..tension1.7..{-sklon1}z6{sklon1}..
#       {sklon1}z7..z8{right}..tension1.7..{-sklon1}z9d..
#       z9{left}..z9p{down}..{sklon2}z10;
#endchar;
z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);
z4=(0,1);    z5=(0.5,0);    z6=(7,14);
z7=(3.8,1);  z8=(4.3,0);
z9=(10.3,14);  z9d=(z9[0]+.5,z9[1]-1);  z9p=(z9[0]-.5,z9[1]-1);
z10=(14.7,14);
add_char("W_", 8.3, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(-sklon1,z6,sklon1),1,
        (z7,sklon1),1,(z8,right),1.7,(z9d,-sklon1),1,
        (z9,left),1,(z9p,down),1,(z10,sklon2)]),
])

#beginchar("X", 15.1u#, 14u#, 0);
#  z1=(2.5,11);  z2=(5.5,14);  z3=(7,12);  z4=(7.1,1);
#  z7=(14,11);  z8=(12,14);  z10=(7,8);  z9=(1,0);  z6=(-.5,3);
#  draw z1{sklon2}..z2{right}..z3--z4;
#  draw z7{dir110}..z8{left}..tension2..z10..tension1.5..{left}z9..{up}z6;
#  dotah shifted (x4,0);
#endchar;
z1=(2.5,11);  z2=(5.5,14);  z3=(7,12);  z4=(7.1,1);
z7=(14,11);  z8=(12,14);  z10=(7,8);  z9=(1,0);  z6=(-.5,3);
z3t=array(z4)-array(z3); z10t=(-1,-2)
add_char("X_", 15.1, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,z3t),None,(z4,None)]),
    _draw2([(z7,dir_(110)),1,(z8,left),2,(z10,z10t),1.5,(z9,left),1,(z6,up)]),
    shift(dotah, (z4[0],0))
])


#beginchar("Y", 10.7u#, 14u#, 7u#);
#  z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
#  z5=(0.5,0);  z6=(7,14);  z7=(5.2,7);
#  draw z1{sklon2}..z2{right}..z3{sklon1}..{sklon1}z4..
#       z5{right}..tension1.7..{-sklon1}z6--z7;
#  smycka shifted (x7, 0);
#endchar;
z1=(-.5,11);  z2=(2.5,14);  z3=(3,12);  z4=(0,1);
z5=(0.5,0);  z6=(7,14);  z7=(5.2,7);
add_char("Y_", 10.7, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z6,-sklon1),None,(z7,None)]),
    shift(smycka, (z7[0],0))
])
add_char("Y_acute", 10.7, [
    _draw2([(z1,sklon2),1,(z2,right),1,(z3,sklon1),1,(z4,sklon1),1,
        (z5,right),1.7,(z6,-sklon1),None,(z7,None)]),
    shift(smycka, (z7[0],0)),
    shift(capcarka, (5.5,0))
])

#beginchar("Z", 12u#, 14u#, 0);
#  z1=(1,12);  z2=(4,14);  z3=(7.5,13);  z4=(9,14);  z4p=(x4+1,y4-.5);
#  z5=(2,1);  z5d=(.5,0);  z5p=(-.5,.8);  z6=(6,0);  z7=(12,6);
#  draw z1..z2{right}..z3..z4p{up}..z4{left}..z3..
#       z5..z5d{left}..z5p{up}..z5..z6{right}..tension2..{sklon2}z7;
#endchar;
z1=(1,12);  z2=(4,14);  z3=(7.5,13);  z4=(9,14);  z4p=(z4[0]+1,z4[1]-.5);
z5=(2,1);  z5d=(.5,0);  z5p=(-.5,.8);  z6=(6,0);  z7=(12,6);
z1t=(1,1); z3t=(1,-1); z3t2=(-1,-2); z5t=(-1,-2); z5t2=(2,-1)
add_char("Z_", 12, [
  _draw2([(z1,z1t),1,(z2,right),1,(z3,z3t),1,(z4p,up),1,(z4,left),1,(z3,z3t2),1,
      (z5,z5t),1,(z5d,left),1,(z5p,up),1,(z5,z5t2),1,(z6,right),2,(z7,sklon2)]),
])
add_char("Z_caron", 12, [
  _draw2([(z1,z1t),1,(z2,right),1,(z3,z3t),1,(z4p,up),1,(z4,left),1,(z3,z3t2),1,
      (z5,z5t),1,(z5d,left),1,(z5p,up),1,(z5,z5t2),1,(z6,right),2,(z7,sklon2)]),
    shift(hacek, (6,6))
])

################################################################################
# Digits

#beginchar("1", 8u#, 14u#, 0);
#  z1=(1.5,9); z2=(5.5,14); z3=(2.5,0);
#  draw z1..{dir60}z2--z3;
#endchar;
z1=(1.5,9); z2=(5.5,14); z3=(2.5,0);
z1t=(1,1)
add_char("one", 8, [
  _draw2([(z1,z1t),1,(z2,dir_(60)),None,(z3,None)]),
])

#beginchar("2", 8u#, 14u#, 0);
#  z1=(1.5,11); z2=(4,14); z3=(6,11); z4=(0,0); z5=(5,0);
#  draw z1..z2{right}..z3{-dir80}..{-dir65}z4--z5;
#endchar;
z1=(1.5,11); z2=(4,14); z3=(6,11); z4=(0,0); z5=(5,0);
z1t=(0,1)
add_char("two", 8, [
  _draw2([(z1,z1t),1,(z2,right),1,(z3,-dir_(80)),1,
      (z4,-dir_(65)),None,(z5,None)]),
])

#beginchar("3", 8u#, 14u#, 0);
#  z1=(1.5,11); z2=(4,14); z3=(6,11); z4=(3,8); z5=(2,0); z6=(-.5,3);
#  draw z1..z2{right}..z3{-dir80}..z4&z4..tension1.5..z5{left}..z6{up};
#endchar;
z1=(1.5,11); z2=(4,14); z3=(6,11); z4=(3,8); z5=(2,0); z6=(-.5,3);
z1t=(0,1)
add_char("three", 8, [
  _draw2([(z1,z1t),1,(z2,right),1,(z3,-dir_(80)),1,(z4,(-1,0))]),
  _draw2([(z4,(4,-1)),1.5,(z5,left),1,(z6,up)]),
])

#beginchar("4", 8u#, 14u#, 0);
#  z1=(5,14); z2=(0,6); z3=(6,6); z4=(4.5,9); z5=(2.5,0);
#  draw z1--z2--z3;
#  draw z4--z5;
#endchar;
z1=(5,14); z2=(0,6); z3=(6,6); z4=(4.5,9); z5=(2.5,0);
add_char("four", 8, [
  _draw2([(z1,None),None,(z2,None),None,(z3,None)]),
  _draw2([(z4,None),None,(z5,None)]),
])

#beginchar("5", 8u#, 14u#, 0);
#  z1=(6,14); z2=(2.5,14); z3=(1,8); z4=(4,9); z5=(2,0); z6=(-.5,3);
#  draw z1--z2--z3&z3..z4..tension1.5..z5{left}..z6{up};
#endchar;
z1=(6,14); z2=(2.5,14); z3=(1,8); z4=(4,9); z5=(2,0); z6=(-.5,3);
z3t=array(z2)-array(z3); z4t=dir_(-42)
add_char("five", 8, [
  _draw2([(z1,None),None,(z2,None),None,(z3,None)]),
  _draw2([(z3,z3t),1,(z4,z4t),1.5,(z5,left),1,(z6,up)]),
])

#beginchar("6", 8u#, 14u#, 0);
#  z1=(6,14); z3=(.5,5); z4=(4,8); z5=(2,0); z6=(-.5,3);
#  draw z1{-dir35}..z3{sklon1}&z3{-sklon1}..z4..tension1.5..z5{left}..
#       z3{-sklon1};
#endchar;
z1=(6,14); z3=(.5,5); z4=(4,8); z5=(2,0); z6=(-.5,3);
z4t=dir_(-38)
add_char("six", 8, [
  _draw2([(z1,-dir_(35)),1,(z3,sklon1)]),
  _draw2([(z3,-sklon1),1,(z4,z4t),1.5,(z5,left),1,(z3,-sklon1)]),
])

#beginchar("7", 8u#, 14u#, 0);
#  z1=(0.5,14); z2=(6,14); z3=(0,0); z4=(1.5,7); z5=(4.5,7);
#  draw z1--z2--z3;
#  draw z4--z5;
#endchar;
z1=(0.5,14); z2=(6,14); z3=(0,0); z4=(1.5,7); z5=(4.5,7);
add_char("seven", 8, [
  _draw2([(z1,None),None,(z2,None),None,(z3,None)]),
  _draw2([(z4,None),None,(z5,None)]),
])

#beginchar("8", 8u#, 14u#, 0);
#  z1=(4,14); z2=(3.2,8); z3=(2,0);
#  draw z1{left}..z2..z3{left}..z2..{left}z1;
#endchar;
z1=(4,14); z2=(3.2,8); z3=(2,0);
z2t=dir_(-57.8); z2t2=dir_(-326)
add_char("eight", 8, [
  _draw2([(z1,left),1,(z2,z2t),1,(z3,left),1,(z2,z2t2),1,(z1,left)]),
])

#beginchar("9", 8u#, 14u#, 0);
#  z0=(2,13); z1=(6,14); z2=(1,7); z3=(2.5,0);
#  z1p=(4,13.9);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.2..{-sklon1}z1{sklon1}..z3{sklon1};
#endchar;
z0=(2,13); z1=(6,14); z2=(1,7); z3=(2.5,0);
z1p=(4,13.9);z1pt=dir_(-168)
add_char("nine", 8, [
  _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
      (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1)]),
])

#beginchar("0", 8u#, 14u#, 0);
#  z1=(4,14); z3=(1,0);
#  draw z1{left}..tension2.9..z3{right}..tension2.9..{left}z1;
#endchar;
z1=(4,14); z3=(1,0);
add_char("zero", 8, [
  _draw2([(z1,left),2.9,(z3,right),2.9,(z1,left)]),
])

################################################################################
# Others

# .notdef
z1=(0.5,14);  z2=(15,14);  z3=(15,0);  z4=(0.5,0);
add_char("_notdef", 15, [
    _draw2([(z1,None),None,(z2,None),None,(z3,None),None,(z4,None),None,
        (z1,None)]),
    _draw2([(z1,None),None,(z3,None)]),
    _draw2([(z2,None),None,(z4,None)]),
])

# space
add_char("space", 115/40, [])

# subs_token
add_char("subs_token", 10/40, [])

#beginchar("+", 8u#, 9u#, 0);
#  z1=(1,7); z2=(6,7); z3=(3.3,4.5); z4=(3.7,9.5);
#  draw z1--z2;
#  draw z3--z4;
#endchar;
z1=(1,7); z2=(6,7); z3=(3.3,4.5); z4=(3.7,9.5);
add_char("plus", 8, [
  _draw2([(z1,None),None,(z2,None)]),
  _draw2([(z3,None),None,(z4,None)]),
])

#beginchar(minus, 8u#, 7u#, 0);
#  z1=(1,7); z2=(6,7);
#  draw z1--z2;
#endchar;
z1=(1,7); z2=(6,7);
add_char("minus", 8, [
  _draw2([(z1,None),None,(z2,None)]),
])

#beginchar(times, 8u#, 9u#, 0);
#  z1=(1.7,9); z2=(5.7,9); z3=(1.3,5); z4=(5.3,5);
#  draw z1--z4;
#  draw z2--z3;
#endchar;
z1=(1.7,9); z2=(5.7,9); z3=(1.3,5); z4=(5.3,5);
add_char("multiply", 8, [
  _draw2([(z1,None),None,(z4,None)]),
  _draw2([(z2,None),None,(z3,None)]),
])

#beginchar("*", 8u#, 9u#, 0);
#  z1=(1.7,10); z2=(5.7,10); z3=(1.3,4); z4=(5.3,4);
#  draw z1--z4;
#  draw z2--z3;
#  draw (0,7)--(7,7);
#endchar;
z1=(1.7,10); z2=(5.7,10); z3=(1.3,4); z4=(5.3,4);
add_char("asterisk", 8, [
  _draw2([(z1,None),None,(z4,None)]),
  _draw2([(z2,None),None,(z3,None)]),
  _draw2([((0,7),None),None,((7,7),None)]),
])

#beginchar("=", 8u#, 9u#, 0);
#  z1=(1,6); z2=(6,6); z3=(1.2,8); z4=(6.2,8);
#  draw z1--z2;
#  draw z3--z4;
#endchar;
z1=(1,6); z2=(6,6); z3=(1.2,8); z4=(6.2,8);
add_char("equal", 8, [
  _draw2([(z1,None),None,(z2,None)]),
  _draw2([(z3,None),None,(z4,None)]),
])

#beginchar(slash, 8u#, 14u#, 0);
#  z1=(0,0); z2=(9,14);
#  draw z1--z2;
#endchar;
z1=(0,0); z2=(9,14);
add_char("slash", 8, [
  _draw2([(z1,None),None,(z2,None)]),
])

#beginchar(backslash, 6u#, 14u#, 0);
#  z1=(0,14); z2=(6,0);
#  draw z1--z2;
#endchar;
z1=(0,14); z2=(6,0);
add_char("backslash", 6, [
  _draw2([(z1,None),None,(z2,None)]),
])

#beginchar("<", 8u#, 14u#, 0);
#  z1=(1,7); z2=(7,10); z3=(6,4);
#  draw z3--z1--z2;
#endchar;
z1=(1,7); z2=(7,10); z3=(6,4);
add_char("less", 8, [
  _draw2([(z3,None),None,(z1,None),None,(z2,None)]),
])

#beginchar(">", 8u#, 14u#, 0);
#  z1=(7,7); z2=(2,10); z3=(1,4);
#  draw z3--z1--z2;
#endchar;
z1=(7,7); z2=(2,10); z3=(1,4);
add_char("greater", 8, [
  _draw2([(z3,None),None,(z1,None),None,(z2,None)]),
])

#beginchar("@", 9u#, 9u#, 2u#);
#  z0=(4,6); z1=(7,7); z2=(3,0); z3=(5.4,1);
#  z1p=(5.5,6.9);
#  z4=(6,0); z5=(9,4);  z6=(7,9);  z7=(1,0);  z8=(7,-1);
#  draw z1{left}..z1p..z0{-sklon2}..tension1.5..
#       z2{right}..tension1.2..{-sklon1}z1{sklon1}..z3{sklon1}..
#       z4{right}..z5..z6..z7{dir-60}..z8;
#endchar;
z0=(4,6); z1=(7,7); z2=(3,0); z3=(5.4,1);
z1p=(5.5,6.9);
z4=(6,0); z5=(9,4);  z6=(7,9);  z7=(1,0);  z8=(7,-1);
z1pt=(-4,-1); z5t=dir_(-285); z6t=dir_(-190); z8t=(1,1)
add_char("at", 9, [
  _draw2([(z1,left),1,(z1p,z1pt),1,(z0,-sklon2),1.5,
      (z2,right),1.2,(-sklon1,z1,sklon1),1,(z3,sklon1),1,
      (z4,right),1,(z5,z5t),1,(z6,z6t),1,(z7,dir_(-60)),1,(z8,z8t)]),
])

#beginchar("(", 8u#, 16u#, 2u#);
#  z1=(7,16); z2=(2,7); z3=(5,-2);
#  draw z1..z2..z3;
#endchar;
z1=(7,16); z2=(2,7); z3=(5,-2);
z1t=(-1,-1); z2t=(0,-1); z3t=(1,-1)
add_char("parenleft", 8, [
  _draw2([(z1,z1t),1,(z2,z2t),1,(z3,z3t)]),
])

#beginchar(")", 8u#, 16u#, 2u#);
#  z1=(3,16); z2=(6,7); z3=(1,-2);
#  draw z1..z2..z3;
#endchar;
z1=(3,16); z2=(6,7); z3=(1,-2);
z1t=(1,-1); z2t=(0,-1); z3t=(-1,-1)
add_char("parenright", 8, [
  _draw2([(z1,z1t),1,(z2,z2t),1,(z3,z3t)]),
])

#beginchar("[", 8u#, 14u#, 2u#);
#  z1=(7,14); z1a=(4,14); z2a=(2,0); z2=(5,0);
#  draw z1--z1a--z2a--z2;
#endchar;
z1=(7,14); z1a=(4,14); z2a=(2,0); z2=(5,0);
add_char("bracketleft", 8, [
  _draw2([(z1,None),None,(z1a,None),None,(z2a,None),None,(z2,None)]),
])

#beginchar("]", 8u#, 14u#, 2u#);
#  z1=(6,14); z1a=(3,14); z2a=(1,0); z2=(4,0);
#  draw z1a--z1--z2--z2a;
#endchar;
z1=(6,14); z1a=(3,14); z2a=(1,0); z2=(4,0);
add_char("bracketright", 8, [
  _draw2([(z1a,None),None,(z1,None),None,(z2,None),None,(z2a,None)]),
])

#beginchar("{", 8u#, 14u#, 0);
#  z1=(7,14); z7=(5.5,0);  z1a=(5,14);  z2a=(3,0);
#  z2-z1a = whatever*(z2a-z1a);  y2=12;
#  z3-z1a = whatever*(z2a-z1a);  y3=9;
#  z4 = (2,7);
#  z5-z1a = whatever*(z2a-z1a);  y5=5;
#  z6-z1a = whatever*(z2a-z1a);  y6=2;
#  draw z1{left}..z2..z3..z4&z4..z5..z6..{right}z7;
#endchar;
z1=(7,14); z7=(5.5,0);  z1a=(5,14);  z2a=(3,0);
z2 = whatever_y(z1a, array(z2a)-array(z1a), 12)
z3 = whatever_y(z1a, array(z2a)-array(z1a), 9)
z4 = (2,7);
z5 = whatever_y(z1a, array(z2a)-array(z1a), 5)
z6 = whatever_y(z1a, array(z2a)-array(z1a), 2)
z2t=sklon1;z3t=sklon1;z5t=sklon1;z6t=sklon1
add_char("braceleft", 8, [
  _draw2([(z1,left),1,(z2,z2t),1,(z3,z3t),1,(z4,left)]),
  _draw2([(z4,right),1,(z5,z5t),1,(z6,z6t),1,(z7,right)]),
])

#beginchar("}", 8u#, 14u#, 0);
#  z1=(2.5,14); z7=(1,0);  z1a=(5,14);  z2a=(3,0);
#  z2-z1a = whatever*(z2a-z1a);  y2=12;
#  z3-z1a = whatever*(z2a-z1a);  y3=9;
#  z4 = (7,7);
#  z5-z1a = whatever*(z2a-z1a);  y5=5;
#  z6-z1a = whatever*(z2a-z1a);  y6=2;
#  draw z1{right}..z2..z3..z4&z4..z5..z6..{left}z7;
#endchar;
z1=(2.5,14); z7=(1,0);  z1a=(5,14);  z2a=(3,0);
z2 = whatever_y(z1a, array(z2a)-array(z1a), 12)
z3 = whatever_y(z1a, array(z2a)-array(z1a), 9)
z4 = (7,7);
z5 = whatever_y(z1a, array(z2a)-array(z1a), 5)
z6 = whatever_y(z1a, array(z2a)-array(z1a), 2)
z2t=sklon1;z3t=sklon1;z5t=sklon1;z6t=sklon1
add_char("braceright", 8, [
  _draw2([(z1,right),1,(z2,z2t),1,(z3,z3t),1,(z4,right)]),
  _draw2([(z4,left),1,(z5,z5t),1,(z6,z6t),1,(z7,left)]),
])

#beginchar(percent, 10u#, 14u#, 0);
#  z1=(0,0); z2=(9,14);  z3=(3,14);  z4=(2,9);
#  draw z1--z2;
#  draw z3..tension2..z4..tension2..cycle;
#  draw (z3..tension2..z4..tension2..cycle) shifted (4,-y4);
#endchar;
z1=(0,0); z2=(9,14);  z3=(3,14);  z4=(2,9);
add_char("percent", 10, [
  _draw2([(z1,None),None,(z2,None)]),
  _draw2([(z3,right),2,(z4,left),2,(z3,right)]),
  shift(_draw2([(z3,right),2,(z4,left),2,(z3,right)]), (4,-z4[1])),
])

#beginchar(promile, 13u#, 14u#, 0);
#  z1=(0,0); z2=(9,14);  z3=(3,14);  z4=(2,9);
#  draw z1--z2;
#  draw z3..tension2..z4..tension2..cycle;
#  draw (z3..tension2..z4..tension2..cycle) shifted (4,-y4);
#  draw (z3..tension2..z4..tension2..cycle) shifted (8,-y4);
#endchar;
z1=(0,0); z2=(9,14);  z3=(3,14);  z4=(2,9);
add_char("perthousand", 13, [
  _draw2([(z1,None),None,(z2,None)]),
  _draw2([(z3,right),2,(z4,left),2,(z3,right)]),
  shift(_draw2([(z3,right),2,(z4,left),2,(z3,right)]), (4,-z4[1])),
  shift(_draw2([(z3,right),2,(z4,left),2,(z3,right)]), (8,-z4[1])),
])

#beginchar("&", 7u#, 11u#, 0);
#  z1=(5,0); z2=(3,7); z3=(4,11); z4=(0,1.5);  z5=(1,0);  z6=(7,7);
#  draw z1..z2..z3{right}..z2..tension2..z4{sklon1}..z5{right}..tension2..
#  {sklon2}z6;
#endchar;
z1=(5,0); z2=(3,7); z3=(4,11); z4=(0,1.5);  z5=(1,0);  z6=(7,7);
z1t=dir_(-253); z2t=dir_(-254); z2t2=dir_(-120);
add_char("ampersand", 7, [
  _draw2([(z1,z1t),1,(z2,z2t),1,(z3,right),1,(z2,z2t2),2,(z4,sklon1),1,
      (z5,right),2,(z6,sklon2)]),
])

#beginchar("$", 8u#, 15u#, 1u#);
#  z1=(8,10.5); z2=(4.5,14); z2a=(1,10.5);
#  z3=(4,7);
#  z4=(3.5,0); z4a=(7,3.5);  z5=(0,3.5);
#  draw z1..z2{left}..z2a..z3..z4a..z4{left}..z5;
#  draw (2.5,-1)--(3.5,15);
#  draw (4.5,-1)--(5.5,15);
#endchar;
z1=(8,10.5); z2=(4.5,14); z2a=(1,10.5);
z3=(4,7);
z4=(3.5,0); z4a=(7,3.5);  z5=(0,3.5);
z1t=(0,1); z2at=(0,-1); z3t=dir_(-30); z4at=(0,-1); z5t=(0,1)
add_char("dollar", 8, [
  _draw2([(z1,z1t),1,(z2,left),1,(z2a,z2at),1,(z3,z3t),1,(z4a,z4at),1,
        (z4,left),1,(z5,z5t)]),
  _draw2([((2.5,-1),None),None,((3.5,15),None)]),
  _draw2([((4.5,-1),None),None,((5.5,15),None)]),
])

#beginchar("#", 11.5u#, 14u#, 0);
#  z1=(0,0); z2=(4,14);  z3=(10.5,0);
#  draw (z1--z2) shifted (2,0);
#  draw (z1--z2) shifted (6,0);
#  draw (z1--z3) shifted (.5,5);
#  draw (z1--z3) shifted (1.3,9);
#endchar;
z1=(0,0); z2=(4,14);  z3=(10.5,0);
add_char("numbersign", 11.5, [
  shift(_draw2([(z1,None),None,(z2,None)]), (2,0)),
  shift(_draw2([(z1,None),None,(z2,None)]), (6,0)),
  shift(_draw2([(z1,None),None,(z3,None)]), (0.5,5)),
  shift(_draw2([(z1,None),None,(z3,None)]), (1.3,9)),
])

#beginchar("|", 2u#, 14u#, 0);
#  z1=(0,0); z2=(2,14);
#  draw (z1--z2)
#endchar;
z1=(0,0); z2=(2,14);
add_char("bar", 2, [
  _draw2([(z1,None),None,(z2,None)]),
])

#beginchar("~", 8u#, 9u#, 0);
#  z1=(0,6); z2=(3,8); z3=(5,6); z4=(8,8);
#  draw z1..z2..z3..z4;
#endchar;
z1=(0,6); z2=(3,8); z3=(5,6); z4=(8,8);
z1t=(0,1); z2t=dir_(-27); z3t=dir_(-27); z4t=(0,1);
add_char("asciitilde", 8, [
  _draw2([(z1,z1t),1,(z2,z2t),1,(z3,z3t),1,(z4,z4t)]),
])

#beginchar(inch, 4u#, 15u#, 0);
#  draw (1.8,15)--(1.5,12);
#  draw (3.8,15)--(3.5,12);
#endchar;
add_char("quotedbl.sc", 4, [
  _draw2([((1.8,15),None),None,((1.5,12),None)]),
  _draw2([((3.8,15),None),None,((3.5,12),None)]),
])

#beginchar("^", 6u#, 14u#, 0);
#  draw (2,12)--(4,14)--(6,12);
#endchar;
add_char("asciicircum", 6, [
  _draw2([((2,12),None),None,((4,14),None),None,((6,12),None)]),
])

#beginchar("_", 8u#, 0, 7u#);
#  draw (0,-7)--(8,-7);
#endchar;
add_char("underscore", 8, [
  _draw2([((0,-7),None),None,((8,-7),None)]),
])



################################################################################
# Punctuation

#beginchar("-", 3u#, 7u#, 0);
#  draw (0,4)--(3,4);
#endchar;
add_char("hyphen", 3, [
    _draw2([((0,4),None),None,((3,4),None)]),
])

#beginchar(dash, 12u#, 7u#, 0);
#  z1=(1,7); z2=(10,7);
#  draw z1--z2;
#endchar;
# TODO: the font has emdash, twoemdash, threeemdash, endash, but none
# of them seem to work; but latex puts two and three hyphens instead.
# We generate the `letter_dash.svg`, but we do not copy it into glyphs.
add_char("dash", 12, [
    _draw2([((1,7),None),None,((10,7),None)]),
])

#beginchar("!", 6u#, 14u#, 0);
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot (2,0);
#  pickup pencircle scaled thin;
#  draw (2.6, 4)..(5,14);
#endchar;
add_char("exclam", 12, [
    shift(dot, (2,0)),
    _draw2([((2.6,4),None),None,((5,14),None)]),
])

#beginchar("?", 8u#, 14u#, 0);
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot (4,0);
#  pickup pencircle scaled thin;
#  z1=(3,12);  z2=(6,14);  z3=(5,8.5);  z4=(4.5,3);  z5=(7,5);
#  draw z1..z2{right}..z3..z4{right}..z5;
#endchar;
z1=(3,12);  z2=(6,14);  z3=(5,8.5);  z4=(4.5,3);  z5=(7,5);
z1t=up; z3t=(-1,-1); z5t=up
add_char("question", 8, [
    shift(dot, (4,0)),
    _draw2([(z1,z1t),1,(z2,right),1,(z3,z3t),1,(z4,right),1,(z5,z5t)]),
])

#beginchar(",", 3u#, 1u#, 0);
#  draw (0,1)--(-1,-2);
#endchar;
add_char("comma", 3, [
    _draw2([((0,1),None),None,((-1,-2),None)]),
])

#beginchar(".", 3u#, 1u#, 0);
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot (0,0);
#  pickup pencircle scaled thin;
#endchar;
add_char("period", 3, [
    shift(dot, (0,0)),
])

#beginchar(":", 4u#, 7u#, 0);
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot (1,0);  drawdot (2,7);
#  pickup pencircle scaled thin;
#endchar;
add_char("colon", 4, [
    shift(dot, (1,0)),
    shift(dot, (2,7)),
])

#beginchar(";", 4u#, 7u#, 0);
#  pickup pencircle scaled (dotkoef*thin);
#  drawdot (2,7);
#  pickup pencircle scaled thin;
#  draw (1,1)--(0,-2);
#endchar;
add_char("semicolon", 4, [
    shift(dot, (2,7)),
    _draw2([((1,1),None),None,((0,-2),None)]),
])

#beginchar(clqq, 4u#, 1u#, 0);
#  draw (0,1)--(-1,-2);
#  draw (2,1)--(1,-2);
#endchar;
add_char("quotedblbase", 4, [
    _draw2([((0,1),None),None,((-1,-2),None)]),
    _draw2([((2,1),None),None,((1,-2),None)]),
])

#beginchar(crqq, 4u#, 15u#, 0);
#  draw (2,15)--(1.5,12);
#  draw (4,15)--(3.5,12);
#endchar;
add_char("quotedblright", 4, [
    _draw2([((2,15),None),None,((1.5,12),None)]),
    _draw2([((4,15),None),None,((3.5,12),None)]),
])
add_char("quotedblleft", 4, [
    _draw2([((2,15),None),None,((1.5,12),None)]),
    _draw2([((4,15),None),None,((3.5,12),None)]),
])
add_char("quotedbl", 4, [
    _draw2([((2,15),None),None,((1.5,12),None)]),
    _draw2([((4,15),None),None,((3.5,12),None)]),
])

#beginchar(leftquota, 4u#, 15u#, 0);
#  draw (0,15){down}..(1,12);
#endchar;
add_char("quoteleft", 4, [
    _draw2([((0,15),down),1,((1,12),(1,-1))]),
])

#beginchar(rightquota, 4u#, 15u#, 0);
#  draw (4,15){down}..(2,12);
#endchar;
add_char("quoteright", 4, [
    _draw2([((4,15),down),1,((2,12),(-1,-1))]),
])
add_char("quotesingle", 4, [
    _draw2([((4,15),down),1,((2,12),(-1,-1))]),
])



################################################################################

# Save

unicode = {
        "space": ["uni0020", "uni00A0"],
        "asciitilde": ["uni007E", "uni223C"],
        "hyphen": ["uni002D", "uni00AD", "uni2010", "uni2011"],
        "quoteleft": ["uni2018"],
        "quoteright": ["uni2019"],
    }

glyphs = [
    ".notdef",
    "space",

    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
    "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",

    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o",
    "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",

    "Aacute", "Adieresis", "Ccaron", "Dcaron", "Eacute", "Ecaron", "Iacute",
    "Lacute", "Lcaron", "Ncaron", "Oacute", "Ocircumflex", "Racute", "Rcaron",
    "Scaron", "Tcaron", "Uacute", "Uring", "Yacute", "Zcaron",

    "aacute", "adieresis", "ccaron", "dcaron", "eacute", "ecaron", "iacute",
    "lacute", "lcaron", "ncaron", "oacute", "ocircumflex", "racute", "rcaron",
    "scaron", "tcaron", "uacute", "uring", "yacute", "zcaron",

    "ampersand",

    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine",

    "period", "comma", "colon", "semicolon", "exclam", "question",
    "quotesingle", "quotedbl", "quoteleft", "quoteright", "quotedblleft",
    "quotedblright", "quotedblbase", "hyphen",

    "underscore", "parenleft", "parenright", "bracketleft", "bracketright",
    "braceleft", "braceright", "slash", "bar", "backslash", "asterisk", "at",
    "numbersign",

    "quotedbl.sc",

    "dollar",

    "percent", "perthousand",

    "plus", "minus", "multiply", "equal", "less", "greater", "asciicircum",
    "asciitilde",


    # Our specific glyphs, not in unicode:

    # Connecting curves
    "begin", "begin_straight", "begin_x", "conn_s", "conn_sv", "conn_P", "end",
    # Alternative versions
    "sleft", "sdepth", "scaronleft", "scarondepth", "bnarrow", "onarrow",
    "oacutenarrow", "ocircumflexnarrow", "vnarrow", "wnarrow",
    # Helper token for OTF glyph substitution
    "subs_token",
]

def fix_name(x):
    """
    Take AGL name and create a filename that works on case insensitive
    filesystems (macOS).
    """
    if x[0] >= "A" and x[0] <= "Z":
        x = x[0] + "_" + x[1:]
    if x[0] == ".":
        x = "_" + x[1:]
    return x

letters = [fix_name(x) for x in glyphs]

glyphs_dir = "../font.ufo/glyphs"
run(f"mkdir -p {glyphs_dir}")
s = ""
for letter in letters:
    s += f"file-open:letter_{letter}.svg; select-by-id: path0; object-stroke-to-path; export-type:svg; export-do\n"
open("commands.txt", "w").write(s)
run("inkscape --shell < commands.txt")
for letter in letters:
    run(f"python svg2glif.py letter_{letter}_out.svg")
    run(f"cp letter_{letter}_out_out3.glif {glyphs_dir}/{letter}.glif")

s = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
\t<dict>
"""
for name in glyphs:
    filename = fix_name(name) + ".glif"
    s += f"\t\t<key>{name}</key>\n"
    s += f"\t\t<string>{filename}</string>\n"
s += """\
\t</dict>
</plist>
"""
open(f"{glyphs_dir}/contents.plist", "w").write(s)

s = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
\t<dict>
\t\t<key>public.glyphOrder</key>
\t\t<array>
"""
for name in glyphs:
    s += f"\t\t\t<string>{name}</string>\n"
s += """\
\t\t</array>
\t</dict>
</plist>
"""
open(f"{glyphs_dir}/../lib.plist", "w").write(s)

s = ""
for name in glyphs:
    s += f"{name}\t{name}"
    if name in unicode:
        s += "\t" + ",".join(unicode[name])
    s += "\n"
open(f"{glyphs_dir}/../../GlyphOrderAndAliasDB", "w").write(s)
