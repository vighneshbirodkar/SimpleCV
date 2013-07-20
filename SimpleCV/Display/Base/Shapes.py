"""
These classes are used to represent the objects drawn on a drawing layer.

**Note**
Not to be confused with classes in Detection.* . In addition to coordinates
thse also store color, alpha and other displaying parameters
"""


class Line(object):
    def __init__(self,start,stop,color ,width,antialias,alpha):
        self.start = start
        self.stop = stop
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha

class Rectangle:
    def __init__(self,pt1,pt2,color ,width,filled,antialias,alpha):
        self.pt1 = pt1
        self.pt2 = pt2
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha

class Polygon:
    def __init__(self,points,color, width, filled, antialias, alpha ):
        self.points = points
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha

class Circle:
    def __init__(self, center, radius, color, width, filled, antialias, alpha ):
        self.conter = center
        self.radius = radius
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha

class Ellipse:
    def __init__(self, center, dimensions, color, width,filled ,antialias ,alpha ):
        
        self.center = center
        self.dimensions = dimensions
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha

class Bezier:
    def __init__(self, points, steps, color, antialias, alpha ):
        self.points = points
        self.steps = steps
        self.color = color
        self.antialias = antialias
        self.alpha = alpha
        
class Text:
    def __init__(self, location,font, size, bold,italic,underline,color,antialias,alpha):
        self.color = color
        self.width = width
        self.antialias = antialias
        self.alpha = alpha


