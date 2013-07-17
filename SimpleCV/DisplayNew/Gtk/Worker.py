from multiprocessing import Process,Pipe
import os
from ..Base import DisplayBase


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
    print srcHeight
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
    def __init__(self,connection,size,type_,title,fit):
        self.connection = connection
        self.size = size
        self.fit = fit
        self.title = title
        self.type_ = type_
        self.cairoContext = None
        Process.__init__(self)
   
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
        self.drawingArea = builder.get_object("drawingArea")
        self.eventBox = builder.get_object("eventbox")
        self.eventBox.set_events(gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)
        
        #when an image arrives, its data is stored here
        self.imageData = None
        
        if(self.type_ == DisplayBase.FULLSCREEN):
            self.window.fullscreen()
        elif(self.type_ == DisplayBase.FIXED):
            self.drawingArea.set_size_request(*self.size)
            self.window.set_resizable(False)
        elif(self.type_ == DisplayBase.DEFAULT):
            #self.drawingArea.set_size_request(*self.size)
            self.eventBox.set_default_size(100,100)
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
        self.drawingArea.queue_draw()
        if(self.type_ == DisplayBase.DEFAULT):
            pass
            #self.drawingArea.set_size_request(data['width'],data['height'])
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

    def handle_leftButtonDownPosition(self, data):
        if self._leftMouseDownPos is not None:
            p = self._clamp(self._leftMouseDownPos)
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseDownPos = None

    def handle_rightButtonDownPosition(self, data):
        if self._rightMouseDownPos is not None:
            p = self._clamp(self._rightMouseDownPos)
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseDownPos = None

    def handle_leftButtonUpPosition(self,data):
        if self._leftMouseUpPos is not None:
            p = self._clamp(self._leftMouseUpPos)
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseUpPos = None

    def handle_rightButtonUpPosition(self,data):
        if self._rightMouseUpPos is not None:
            p = self._clamp(self._rightMouseUpPos)
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseUpPos = None
    
    def drawShape(self,shape):
        #print shape
        pass

    def handle_middleButtonDownPosition(self,data):
        if self._middleMouseDownPos is not None:
            p = self._clamp(self._middleMouseDownPos)
        else:
            p = None
        self.connection.send((p,))
        self._middleMouseDownPos = None

    def handle_middleButtonUpPosition(self,data):
        if self._middleMouseUpPos is not None:
            p = self._clamp(self._middleMouseUpPos)
        else:
            p = None
        self.connection.send((p,))
        self._middleMouseUpPos = None

    def handle_mouseScrollPosition(self,data):
        if self._scrollPos is not None:
            p = self._clamp(self._scrollPos)
        else:
            p = None
        self.connection.send((p,))
        self._scrollPos = None

    def handle_mouseScrollType(self,data):
        self.connection.send((self._scrollDir,))
        self._scrollDir = None

    def draw(self,widget,eventData = None):
        data = self.imageData
        if(self.imageData != None ):
            pix =  self.gtk.gdk.pixbuf_new_from_data(data['data'], self.gtk.gdk.COLORSPACE_RGB, False, data['depth'], data['width'], data['height'], data['width']*3)
            
            
            areaWidth = self.drawingArea.get_allocation().width
            areaHeight = self.drawingArea.get_allocation().height
            
            if(self.fit == DisplayBase.CROP):
                pix = smartCrop(self.gtk.gdk,pix,(areaWidth,areaHeight))
            elif(self.fit == DisplayBase.RESIZE):
                pix = smartScale(self.gtk.gdk,pix,(areaWidth,areaHeight))
            else:
                pass
                


            cr = widget.window.cairo_create()

                
            offx,offy = getCentreOffset((areaWidth,areaHeight), (pix.get_width(),pix.get_height()))
            cr.set_source_pixbuf(pix,offx,offy)
            cr.paint()

        #img = Image('lenna')
        #pix =  self.gtk.gdk.pixbuf_new_from_data(img.toSring(), self.gtk.gdk.COLORSPACE_RGB, False, img.depth,img.width, img.height, img.width*3)
        
        
            


