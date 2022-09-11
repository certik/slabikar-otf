from numpy import array, sqrt, arctan2, sin, cos

def arg(z):
    # NumPy's arctan2(y,x) is equal to the arg(x,y) before equation (2) in [1]
    return arctan2(z[1], z[0])

def compute_control_points(z1, z2, w1, w2, tau):
    """
    z1, z2 ... the Bezier nodes (1st and 4th control point)
    w1, w2 ... tangent vectors (do not have to be unit vectors), just direction
    tau ... tension (0.75 .. oo)

    The formulas are implemented from [1], equations (3) and (10).

    Note: the unit tangent vector always points along the direction of the
    curve, so the first point "in" the curve, but the second points "out".

    [1] John D. Hobby: Smooth, Easy to Compute Interpolating Splines. 1985. CS-TR-85-1047.
        Online link: http://i.stanford.edu/pub/cstr/reports/cs/tr/85/1047/CS-TR-85-1047.pdf
    """
    z1 = array(z1)
    z2 = array(z2)
    tau1 = tau2 = tau

    # Metafont parameters, paragraph after (10) in [1]
    a = sqrt(2)
    b = 1/16
    c = (3-sqrt(5))/2

    # Paragraph above equation (2) in [1]
    theta = arg(w1) - arg(z2-z1)
    phi   = arg(z2-z1) - arg(w2)

    # Equations (10) in [1]
    alpha = a * (sin(theta) - b*sin(phi)) * (sin(phi) - b*sin(theta)) \
              * (cos(theta) -   cos(phi))
    rho   = (2 + alpha) / (1 + (1-c)*cos(theta) + c*cos(phi  ))
    sigma = (2 - alpha) / (1 + (1-c)*cos(phi  ) + c*cos(theta))

    # Paragraph above equation (3) in [1]
    c1 = rho/(3*tau1) * array([cos(theta), sin(theta)])
    c2 = array([1 - sigma/(3*tau2) * cos(phi), sigma/(3*tau2) * sin(phi)])

    # Shift and rotate the control points from (0,0)-(1,0) to z1-z2; equation (2) in [1]
    c1 = z1 + array([
        (z2[0]-z1[0])*c1[0]+(z1[1]-z2[1])*c1[1],
        (z2[1]-z1[1])*c1[0]+(z2[0]-z1[0])*c1[1]
        ])
    c2 = z1 + array([
        (z2[0]-z1[0])*c2[0]+(z1[1]-z2[1])*c2[1],
        (z2[1]-z1[1])*c2[0]+(z2[0]-z1[0])*c2[1]
        ])

    return c1, c2
