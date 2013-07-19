from multiprocessing import Process,Pipe
import os
from ..Base import DisplayBase
from ..Base import Line


def getCentreOffset(box1,box2):
    return (box1[0] - box2[0])/2, (box1[1] - box2[1])/2 



#returns x,y,xScale,yScale
#copied from adaptiveScale in ImageClass
def smartScale(gdk, src, resolution):
    srcWidth = src.get_width()
    srcHeight = src.get_height()
    srcSize = srcWidth,srcHeight

    wndwAR = float(resolution[0])/float(resolution[1])
    imgAR = float(srcWidth)/float(srcHeight)

    targetx = 0
    targety = 0
    targetw = resolution[0]
    targeth = resolution[1]

    if( srcSize == resolution): # we have to resize
        return src
    elif( imgAR == wndwAR ):
        wScale = float(resolution[0])/srcWidth
        hScale = float(resolution[1])/srcHeight 
        return src.scale_simple(resolution[0],resolution[1],gdk.INTERP_BILINEAR)
    else:
        #scale factors

        wscale = (float(srcWidth)/float(resolution[0]))
        hscale = (float(srcHeight)/float(resolution[1]))
        if(wscale>1): #we're shrinking what is the percent reduction
            wscale=1-(1.0/wscale)
        else: # we need to grow the image by a percentage
            wscale = 1.0-wscale
        if(hscale>1):
            hscale=1-(1.0/hscale)
        else:
            hscale=1.0-hscale
        if( wscale == 0 ): #if we can get away with not scaling do that
            targetx = 0
            targety = (resolution[1]-srcHeight)/2
            targetw = srcWidth
            targeth = srcHeight
        elif( hscale == 0 ): #if we can get away with not scaling do that
            targetx = (resolution[0]-srcWidth)/2
            targety = 0
            targetw = srcWidth
            targeth = srcHeight
        elif(wscale < hscale): # the width has less distortion
            sfactor = float(resolution[0])/float(srcWidth)
            targetw = int(float(srcWidth)*sfactor)
            targeth = int(float(srcHeight)*sfactor)
            if( targetw > resolution[0] or targeth > resolution[1]):
                #aw shucks that still didn't work do the other way instead
                sfactor = float(resolution[1])/float(srcHeight)
                targetw = int(float(srcWidth)*sfactor)
                targeth = int(float(srcHeight)*sfactor)
                targetx = (resolution[0]-targetw)/2
                targety = 0
            else:
                targetx = 0
                targety = (resolution[1]-targeth)/2

        else: #the height has more distortion
            sfactor = float(resolution[1])/float(srcHeight)
            targetw = int(float(srcWidth)*sfactor)
            targeth = int(float(srcHeight)*sfactor)
            if( targetw > resolution[0] or targeth > resolution[1]):
                #aw shucks that still didn't work do the other way instead
                sfactor = float(resolution[0])/float(srcWidth)
                targetw = int(float(srcWidth)*sfactor)
                targeth = int(float(srcHeight)*sfactor)
                targetx = 0
                targety = (resolution[1]-targeth)/2
            else:
                targetx = (resolution[0]-targetw)/2

    return src.scale_simple(targetw,targeth,gdk.INTERP_BILINEAR)


def smartCrop(gdk,src,resolution):
    srcWidth = src.get_width()
    srcHeight = src.get_height()
    srcSize = srcWidth,srcHeight

    wndwAR = float(resolution[0])/float(resolution[1])
    imgAR = float(srcWidth)/float(srcHeight)

    targetx = 0
    targety = 0
    targetw = resolution[0]
    targeth = resolution[1]
    x,y = None,None
    if(srcWidth <= resolution[0] and srcHeight <= resolution[1] ): # center a too small image
        #we're too small just center the thing
        targetx = (resolution[0]/2)-(srcWidth/2)
        targety = (resolution[1]/2)-(srcHeight/2)
        targeth = srcHeight
        targetw = srcWidth
        x,y = 0,0
    elif(srcWidth > resolution[0] and srcHeight > resolution[1]): #crop too big on both axes
        targetw = resolution[0]
        targeth = resolution[1]
        targetx = 0
        targety = 0
        x = (srcWidth-resolution[0])/2
        y = (srcHeight-resolution[1])/2

    elif( srcWidth <= resolution[0] and srcHeight > resolution[1]): #height too big
        #crop along the y dimension and center along the x dimension
        targetw = srcWidth
        targeth = resolution[1]
        targetx = (resolution[0]-srcWidth)/2
        targety = 0
        x = 0
        y = (srcHeight-resolution[1])/2

    elif( srcWidth > resolution[0] and srcHeight <= resolution[1]): #width too big
        #crop along the y dimension and center along the x dimension
        targetw = resolution[0]
        targeth = srcHeight
        targetx = 0
        targety = (resolution[1]-srcHeight)/2
        x = (srcWidth-resolution[0])/2
        y = 0
    
    dst = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8, targetw, targeth)
    src.copy_area(x, y, targetw, targeth, dst, 0, 0)

    return dst
    

class GtkWorker(Process):
    """
    A Process for handling a single Display window. Each GtkDisplay window has
    one instance of this class. For each task the GtkDisplay sends a message
    to it's GtkWorker.
    
    Each GUI function (*) in GtkDisplay has a corresponding handle_* method in
    GtkWorker . 
    
    eg. GtkDisplay.showImage() corresponds to GtkWorker.handle_showImage()
    
    
    """
    _gladeFile = "main.glade"
    BGCOLOR = (.5,.5,1.0)
    def __init__(self,connection,size,type_,title,fit):
        Process.__init__(self)
        self.connection = connection
        self.size = size
        self.fit = fit
        self.title = title
        self.type_ = type_
        self.cairoContext = None
        self.daemon = True

    def run(self):
        #Gtk imports have to be done in run, Otherwise Gtk thknks there are
        #multiple copies of itself
        import gtk
        import gobject
        self.gtk = gtk
        
        
        #Loads the GUI from file and connects signals
        builder = gtk.Builder()
        path = os.path.dirname(__file__) + os.sep + GtkWorker._gladeFile
        builder.add_from_file(path)
        builder.connect_signals(self)
        
        
        self.window = builder.get_object("window")
        self.scrolledwindow = builder.get_object("scrolledWindow")
        self.drawingArea = gtk.DrawingArea()
        self.drawingArea.set_events(gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)
        self.drawingArea.connect("expose-event",self.draw)
        self.scrolledwindow.add_with_viewport(self.drawingArea)
        self.scrolledwindow.set_policy(gtk.POLICY_NEVER,gtk.POLICY_NEVER)
        
        #when an image arrives, its data is stored here
        self.imageData = None
        
        #the pixbuf used to load image
        self.pixbuf = None
        
        #the real size of image being displayed originally
        self.imgRealSize = None
        
        #the size of the image, as it appears on the screen
        self.imgDisplaySize = None
        
        #the x and y scale
        self.scale = None
        
        #the offset from the drawing layer at which image is drawn
        self.offset = None
        
        if(self.type_ == DisplayBase.FULLSCREEN):
            self.window.fullscreen()
        elif(self.type_ == DisplayBase.FIXED):
            self.drawingArea.set_size_request(*self.size)
            self.window.set_resizable(False)
        elif(self.type_ == DisplayBase.DEFAULT):
            #self.drawingArea.set_size_request(*self.size)
            self.drawingArea.set_size_request(*self.size)
        else:
            pass

        self.window.set_title(self.title)
        self.window.show_all()


        self._winWidth, self._winHeight = self.window.get_size()
        self._mouseX = None
        self._mouseY = None

        self._leftMouseDownPos = None
        self._rightMouseDownPos = None
        self._leftMouseUpPos = None
        self._rightMouseUpPos = None
        self._middleMouseDownPos = None
        self._middleMouseUpPos = None
        self._scrollPos = None
        self._scrollDir = None

        #calls pollMsg when gtk is idle
        gobject.idle_add(self.pollMsg,None)

        
        gtk.main()

    def pollMsg(self,data=None):

  
        #check if there is any data to be read, wait for 100ms
        #Is used because select.select/poll and gobject.idle_add dont work on windows
        dataThere = self.connection.poll(.10)
        #handle data if it's there
        if(dataThere):
            self.checkMsg()
            
        #required so that event handler stays enabled
        return True
        
    def checkMsg(self):
        
        #examine the message and figure out what to do with it
        msg = self.connection.recv()

        if(type(msg) is dict):
            funcName = "handle_" + msg['function']
            funcToCall = self.__getattribute__(funcName)
            funcToCall(msg)
        else:
            self.drawShape(msg) 
            
    def handle_showImage(self,data):
        #show image from string

        self.imageData = data
        self.imgRealSize = (data['width'],data['height'])
        
        self.pixbuf =  self.gtk.gdk.pixbuf_new_from_data(data['data'], self.gtk.gdk.COLORSPACE_RGB, False, data['depth'], data['width'], data['height'], data['width']*3)
        
        self.drawingArea.queue_draw()
        
        if(self.type_ == DisplayBase.DEFAULT):
            self.drawingArea.set_size_request(data['width'],data['height'])
        elif(self.type_ == DisplayBase.FIXED):
            pass

        
        
        #print self.image.size_request()
        
    def handle_close(self,widget,data=None):
        self.connection.send('Kill Me')
        self.window.hide()
        
        #Calling gtk.main_quit() stalls the parent application. This is because
        #The child quits and parent blocks till the child ca receive
        #
        #Instead we send the parent a message so that it terminates the child.
        #This we the child can continue to receive a message that the parent 
        #might be sending and the parent knows exactly when the display is 
        #closed
        
    def handle_getImageWidgetSize(self,data):
        self.connection.send((self.drawingArea.get_allocation().width,self.drawingArea.get_allocation().height))

    def handle_configure_event(self,widget,event):
        self._winWidth = event.width
        self._winHeight = event.height

    def handle_mouseX(self,data):
        self._mouseX = self.image.get_pointer() [0]
        if self._mouseX < 0:
            self._mouseX = 0
        if self._mouseX > self.drawingArea.get_allocation().width:
            self._mouseX = self.drawingArea.get_allocation().width
        self.connection.send((self._mouseX,))

    def handle_mouseY(self,data):
        self._mouseY = self.image.get_pointer() [1]
        if self._mouseY < 0:
            self._mouseY = 0
        if self._mouseY > self.drawingArea.get_allocation().height:
            self._mouseY = self.drawingArea.get_allocation().height
        self.connection.send((self._mouseY,))

    def mouse_press(self,widget,event):
        if event.button == 1 :
            self._leftMouseDownPos = (event.x,event.y)
        if event.button == 2 :
            self._middleMouseDownPos = (event.x,event.y)
        if event.button == 3:
            self._rightMouseDownPos = (event.x,event.y)

    def mouse_release(self,widget,event):
        if event.button == 1 :
            self._leftMouseUpPos = (event.x,event.y)
        if event.button == 2 :
            self._middleMouseUpPos = (event.x,event.y)
        if event.button == 3:
            self._rightMouseUpPos = (event.x,event.y)

    def mouse_scroll(self,widget,event):
        self._scrollPos = (event.x,event.y)
        if str(event.direction) == '<enum GDK_SCROLL_UP of type GdkScrollDirection>':
            self._scrollDir = 'up'
        elif str(event.direction) == '<enum GDK_SCROLL_DOWN of type GdkScrollDirection>':
            self._scrollDir = 'down'

    def _clamp(self,pos):
        pos = list(pos)
        if pos[0] < 0:
            pos[0] = 0
        elif pos[0] > self.drawingArea.get_allocation().width:
            pos[0] = self.drawingArea.get_allocation().width
        if pos[1] < 0:
            pos[1] = 0
        elif pos[1] > self.drawingArea.get_allocation().height:
            pos[1] = self.drawingArea.get_allocation().height
        return tuple(pos)

    def _mouseOffset(self,pos):
        diff = self.getTopLeft()
        return (pos[0]-diff[0],pos[1]-diff[1])


    def handle_leftButtonDownPosition(self, data):
        if self._leftMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._leftMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseDownPos = None

    def handle_rightButtonDownPosition(self, data):
        if self._rightMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._rightMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseDownPos = None

    def handle_leftButtonUpPosition(self,data):
        if self._leftMouseUpPos is not None:
            p = self._clamp(self._mouseOffset(self._leftMouseUpPos))
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseUpPos = None

    def handle_rightButtonUpPosition(self,data):
        if self._rightMouseUpPos is not None:
            p = self._clamp(self._mouseOffset(self._rightMouseUpPos))
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseUpPos = None

    def handle_middleButtonDownPosition(self,data):
        if self._middleMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._middleMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._middleMouseDownPos = None

    def handle_middleButtonUpPosition(self,data):
        if self._middleMouseUpPos is not None:
            p = self._clamp(self._mouseOffset(self._middleMouseUpPos))
        else:
            p = None
        self.connection.send((p,))
        self._middleMouseUpPos = None

    def handle_mouseScrollPosition(self,data):
        if self._scrollPos is not None:
            p = self._clamp(self._mouseOffset(self._scrollPos))
        else:
            p = None
        self.connection.send((p,))
        self._scrollPos = None

    def handle_mouseScrollType(self,data):
        self.connection.send((self._scrollDir,))
        self._scrollDir = None

    def draw(self,widget,eventData = None):
        if(self.pixbuf == None):
            return
        if(self.type_ == DisplayBase.DEFAULT):
            self.drawingArea.set_size_request(10,10)

        areaWidth = self.drawingArea.get_allocation().width
        areaHeight = self.drawingArea.get_allocation().height
        
        if(self.fit == DisplayBase.CROP):
            pix = smartCrop(self.gtk.gdk,self.pixbuf,(areaWidth,areaHeight))
        elif(self.fit == DisplayBase.RESIZE):
            pix = smartScale(self.gtk.gdk,self.pixbuf,(areaWidth,areaHeight))
        else:
            pass
            
        cr = widget.window.cairo_create()

        #cr.scale(areaWidth,areaHeight)    
        self.imgDisplaySize =  (pix.get_width(),pix.get_height())
        offx,offy = getCentreOffset((areaWidth,areaHeight),self.imgDisplaySize)
        self.offset = offx,offy
        self.scale = float(self.imgDisplaySize[0])/self.imgRealSize[0] , float(self.imgDisplaySize[1])/self.imgRealSize[1]
        
        cr.set_source_rgb(*GtkWorker.BGCOLOR) # blue
        cr.rectangle(0, 0, areaWidth, areaHeight)
        cr.fill()
        #TODO optimize
        tl = self.getTopLeft()
        wh = self.getCropWH()
        x,y,w,h = tl[0],tl[1],wh[0],wh[1]

        cr.rectangle(x,y,w,h)
        #cr.stroke()
        cr.clip()
        cr.set_source_pixbuf(pix,offx,offy)
        cr.paint()
        cr.translate(*self.getTopLeft())
        if(self.fit == DisplayBase.CROP):
            cr.scale(1,1)
        else:
            cr.scale(self.scale[0],self.scale[1])
        self.drawLayers(cr)
        
    def drawLayers(self,context):
        if(self.imageData is None):
            return
        layers = self.imageData['layers']
        for layer in layers:
            
            for shape in layer.shapes():
                self.drawShape(context,shape)
            
    def drawShape(self,cr,shape):
        if(type(shape) == Line):
            r,g,b = shape.color
            r,g,b = float(r)/255,float(g)/255,float(b)/255
            a = float(shape.alpha)/255
            cr.set_source_rgba(r,g,b,a)
            cr.set_line_width(shape.width)
            cr.move_to(*shape.start)
            cr.line_to(*shape.stop)
            cr.stroke()

    def getTopLeft(self):
        if(self.fit == DisplayBase.RESIZE):
            return self.offset
        elif(self.fit == DisplayBase.CROP):
            areaWidth = self.drawingArea.get_allocation().width
            areaHeight = self.drawingArea.get_allocation().height
            return areaWidth/2 - self.imgRealSize[0]/2 , areaHeight/2 - self.imgRealSize[1]/2
    
    def getCropWH(self):
        if(self.fit == DisplayBase.RESIZE):
            return self.imgDisplaySize
        elif(self.fit == DisplayBase.CROP):
            return self.imageData['width'],self.imageData['height']

