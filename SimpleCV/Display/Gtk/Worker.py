from multiprocessing import Process,Pipe
import os
from ..Base import Display
from ..Base import Display
from ..Base import Line
from ..Base.Display import *
import numpy as np
from ... import Image


#returns x,y,xScale,yScale
#copied from adaptiveScale in ImageClass
def smartScale(gdk, src, resolution):
    """
    **SUMMARY**
    
    Resizes an image preserving its aspect ratio. Copied from adaptive scale.
    Is used to resize image for the display
    
    **PARAMETERS**
    
    * *gdk* - A gdk module object
    
    * *src* - The source pixbuf ( gtk.gdk.pixbuf )
    
    * *resolution*  - The desired resouution to scale to.
    
    **RETURNS**
    
    A resized pixbuf.
    
    """
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


class GtkWorker(Process):
    """
    A Process for handling a single Display window. Each GtkDisplay window has
    one instance of this class. For each task the GtkDisplay sends a message
    to it's GtkWorker.All communicattion happens over a duplex pipe.
    
    Each GUI function (*) in GtkDisplay has a corresponding handle_* method in
    GtkWorker . 
    
    eg. GtkDisplay.showImage() corresponds to GtkWorker.handle_showImage()
    
    
    """
    
    #the glade file contatning the gtk GUI layout
    _gladeFile = "main.glade"
    BGCOLOR = (.5,.5,1.0)
    def __init__(self,connection,size,type_,title,fit):
        """
        **SUMMARY**
        
        Creates a new process to handle the gtk mainloop for a display.
        
        **PARAMETERS**
        
        * *connection* - The connection used to communicate with parent
         
        * *size* - Initial size of display.
        
        * *type_* - The type of dispay.
        
        * *fit* - the fitting methods of the display.
        
        """
        #TODO , the doc references
        Process.__init__(self)
        self.connection = connection
        self.size = size
        self.fit = fit
        self.title = title
        self.type_ = type_
        self.daemon = True

    def run(self):
        """
        **SUMMARY**
        
        Loads the layout from the glade file and starts the gtk mainloop
        
        """
        #Gtk imports have to be done in run, Otherwise Gtk thknks there are
        #multiple copies of itself. These will be local to each process
        import gtk
        import gobject
        self.gtk = gtk
        
        
        #Loads the GUI from file and connects signals
        builder = gtk.Builder()
        path = os.path.dirname(__file__) + os.sep + GtkWorker._gladeFile
        builder.add_from_file(path)
        builder.connect_signals(self)
        
        #get required wigdets
        self.window = builder.get_object("window")
        self.scrolledWindow = builder.get_object("scrolledWindow")
        self.drawingArea = gtk.DrawingArea()
        self.drawingArea.set_events(gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK|gtk.gdk.POINTER_MOTION_MASK)

        
        #glade doesnt seem to have expose-event
        self.drawingArea.connect("expose-event",self.draw)

        self.drawingArea.connect("button_press_event",self.mouse_press)
        self.drawingArea.connect("button_release_event",self.mouse_release)
        self.drawingArea.connect("scroll_event",self.mouse_scroll)
        self.drawingArea.connect("motion_notify_event", self.mouse_motion)

        
        self.scrolledWindow.add_with_viewport(self.drawingArea)
        self.viewPort = self.scrolledWindow.children()[0]

        #when an image arrives, its data is stored here, a dict type when not None
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
        
        #the image being displayed, a simplecv Image object, set only when
        #necessary
        self.image = None
        
        self.window.set_title(self.title)
        self.window.show_all()


        self._winWidth, self._winHeight = self.window.get_size()
        self._position = None
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

        if(self.type_ == Display.FULLSCREEN):
            self.window.fullscreen()
        elif(self.type_ == Display.FIXED):
            self.drawingArea.set_size_request(*self.size)
            self.window.set_resizable(False)
        elif(self.type_ == Display.DEFAULT):
            #self.drawingArea.set_size_request(*self.size)
            self.drawingArea.set_size_request(*self.size)
        else:
            raise ValueError("The Display type was not understood")
            
        if(self.fit == Display.RESIZE):
            self.scrolledWindow.set_policy(self.gtk.POLICY_NEVER, self.gtk.POLICY_NEVER)
        elif(self.fit == Display.SCROLL):
            print 'scroll'
            self.scrolledWindow.set_policy(self.gtk.POLICY_AUTOMATIC, self.gtk.POLICY_AUTOMATIC)
        else:
            raise ValueError("The fit method was not understood")

        #calls pollMsg when gtk is idle.
        #Gtk calls this function when it has nothing else to do. This ensures 
        #that the worker repeatedly checks for arriving messages
        gobject.idle_add(self.pollMsg,None)

        
        gtk.main()

    def pollMsg(self,data=None):
        """
        
        **SUMMARY** 
        
        Checks the connection to see id there are any requests from the parent
        
        **PARAMETERS**
        
        * *data* - Required for the gtk callback, always None.
        
        """

  
        #check if there is any data to be read, wait for 10ms
        #Is used because select.select/poll and gobject.idle_add dont work on windows
        dataThere = self.connection.poll(.001)
        
        #handle data if it's there
        if(dataThere):
            self.checkMsg()
            
        #required so that event handler stays enabled
        return True
        
    def checkMsg(self):
        """
        
        **SUMMARY**
        
        Reads the message from the parent and figures out what to do
        
        """
        
        #examine the message and figure out what to do with it
        msg = self.connection.recv()

        # A request from parent for the function 'XX' will call 'handle_XX' over
        # here

        funcName = "handle_" + msg['function']
        funcToCall = self.__getattribute__(funcName)
        funcToCall(msg)

            
    def handle_showImage(self,data):
        """
        
        **SUMMARY**
        
        Display the image requested by the parent
        
        **PARAMETERS**
        
        * *data* - The dict sent by the parent contaning the image data.
        
        """
        #show image from string
    
        #invalidate existing image
        self.image = None
        self.imageData = data
        self.imgRealSize = (data['width'],data['height'])
        
        #convert the string to a pixbuf
        self.pixbuf =  self.gtk.gdk.pixbuf_new_from_data(data['data'], self.gtk.gdk.COLORSPACE_RGB, False, data['depth'], data['width'], data['height'], data['width']*3)
        
        # tell gtk to draw again
        self.drawingArea.queue_draw()
        
        if(self.type_ == Display.DEFAULT):
            #enlarge display to show the image
            self.viewPort.set_size_request(data['width']+25,data['height']+25)
        elif(self.type_ == Display.FIXED):
            pass
        
    def handle_close(self,widget,data=None):
    
        #http://img.tapatalk.com/d/12/09/13/4yzanezu.jpg
        self.connection.send('Kill Me')
        self.window.hide()
        
        #Calling gtk.main_quit() stalls the parent application. This is because
        #The child quits and parent blocks till the child can receive data
        #
        #Instead we send the parent a message so that it terminates the child.
        #This way the child can continue to receive a message that the parent 
        #might be sending and the parent knows exactly when the display is 
        #closed. 
        #
        #Closing merely hides the display. The parent terminate the process
        #when it reads 'Kill Me'
        
    def handle_getImageWidgetSize(self,data):
        """
        
        **SUMMARY**
        
        Send the area occupied by drawingArea to parent.
        
        """
        self.connection.send((self.drawingArea.get_allocation().width,self.drawingArea.get_allocation().height))

    def handle_configure_event(self,widget,event):
        self._winWidth = event.width
        self._winHeight = event.height

    def handle_mouseX(self,data):
        if self._position is not None:
            pos = self._clamp(self._mouseOffset(self._position))[0]
        else:
            pos = None
        self.connection.send(pos)
        
    def handle_mouseY(self,data):
        if self._position is not None:
            pos = self._clamp(self._mouseOffset(self._position))[1]
        else:
            pos = None
        self.connection.send(pos)
        
    def mouse_motion(self,widget,event):
        self._position = (event.x,event.y)

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
        elif pos[0] > self.imgDisplaySize[0]:
            pos[0] = self.imgDisplaySize[0]
        if pos[1] < 0:
            pos[1] = 0
        elif pos[1] > self.imgDisplaySize[1]:
            pos[1] = self.imgDisplaySize[1]
        return tuple(pos)

    def _mouseOffset(self,pos):
        diff = self.offset
        return (pos[0]-diff[0],pos[1]-diff[1])


    def handle_leftDown(self, data):
        if self._leftMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._leftMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseDownPos = None

    def handle_rightDown(self, data):
        if self._rightMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._rightMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseDownPos = None

    def handle_leftUp(self,data):
        if self._leftMouseUpPos is not None:
            p = self._clamp(self._mouseOffset(self._leftMouseUpPos))
        else:
            p = None
        self.connection.send((p,))
        self._leftMouseUpPos = None

    def handle_rightUp(self,data):
        if self._rightMouseUpPos is not None:
            p = self._clamp(self._mouseOffset(self._rightMouseUpPos))
        else:
            p = None
        self.connection.send((p,))
        self._rightMouseUpPos = None

    def handle_middleDown(self,data):
        if self._middleMouseDownPos is not None:
            p = self._clamp(self._mouseOffset(self._middleMouseDownPos))
        else:
            p = None
        self.connection.send((p,))
        self._middleMouseDownPos = None

    def handle_middleUp(self,data):
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
        """
        
        **SUMMARY**
        
        Does the actual displaying of the received image data
        
        **PARAMETERS**
        
        * *widget* - The widget to draw on. In this case, drawingArea
        
        * *eventData* - None always
        
        """
        
        if(self.pixbuf == None):
            return
        if(self.type_ == Display.DEFAULT):
            #so that window can be resized to almost any size later
            self.scrolledWindow.set_size_request(10,10)  
    
        if(self.fit == Display.SCROLL):
            #no resizing required
            pix = self.pixbuf
        elif(self.fit == Display.RESIZE):
            #resize the image to fit drawingArea
            areaWidth = self.drawingArea.get_allocation().width
            areaHeight = self.drawingArea.get_allocation().height
            pix = smartScale(self.gtk.gdk,self.pixbuf,(areaWidth,areaHeight))
            
        cr = widget.window.cairo_create()

        #cr.scale(areaWidth,areaHeight)    
        if(self.fit == Display.SCROLL):
            #No scaling, no offset, the image is displayed as is. Scrollbars
            #take care of the excess part
            self.imgDisplaySize = self.imgRealSize
            self.offset = 0,0
            self.scale = 1,1
            self.drawingArea.set_size_request(*self.imgRealSize)
        elif(self.fit == Display.RESIZE):
            # reduce the request so the window can be shrunk to lesser than the
            # image size
            self.drawingArea.set_size_request(10,10)
            
            self.imgDisplaySize =  (pix.get_width(),pix.get_height())
            self.offset = self.getCentreOffset()
            self.scale = float(self.imgDisplaySize[0])/self.imgRealSize[0] , float(self.imgDisplaySize[1])/self.imgRealSize[1]
            
            #paint the background
            cr.set_source_rgb(*GtkWorker.BGCOLOR) # blue
            cr.rectangle(0, 0, areaWidth, areaHeight)
            cr.fill()
        
        # clip, so that drawings dont go outside the image
        x,y,w,h = self.offset[0],self.offset[1],self.imgDisplaySize[0],self.imgDisplaySize[1]
        cr.rectangle(x,y,w,h)
        cr.clip()
        
        #draw the image
        cr.set_source_pixbuf(pix,self.offset[0],self.offset[1])
        cr.paint()
        
        #scale and translate the drawings
        cr.translate(*self.offset)
        cr.scale(*self.scale)
        
        self.drawLayers(cr)
        
    def drawLayers(self,context):
        """
        
        **SUMMARY**
        
        Draws the layers of the image
        
        **PARAMETERS**
        
        * *context* - The Cairo Context to be used for drawing.
        
        """
        if(self.imageData is None):
            return
        layers = self.imageData['layers']
        for layer in layers:
            
            for shape in layer.shapes():
                self.drawShape(context,shape)
            
    def drawShape(self,cr,shape):
        """
        
        **SUMMARY**
        
        Draws a shape on the image
        
        **PARAMETERS**
        
        * *cr* - The cairo context to draw on
        
        * *shape* - The shape to draw
        
        """
        if(type(shape) == Line):
            r,g,b = shape.color
            r,g,b = float(r)/255,float(g)/255,float(b)/255
            a = float(shape.alpha)/255
            cr.set_source_rgba(r,g,b,a)
            cr.set_line_width(shape.width)
            cr.move_to(*shape.start)
            cr.line_to(*shape.stop)
            cr.stroke()

    def getCentreOffset(self):
        """
        
        **SUMMARY**
        
        Returns the offset ( the amount by which top-left corener is displaced)
        of the image.
        
        **RETURNS**
        
        A (x,y) tuple.
        
        """
        area = self.drawingArea.get_allocation().width, self.drawingArea.get_allocation().height
        imgSize = self.imgDisplaySize
        return (area[0] - imgSize[0])/2, (area[1] - imgSize[1])/2 
    
    def getImage(self):
        """
        
        **SUMMARY** 
        
        Converts received data into a SimpleCV image.
        
        **RETURNS**
        
        A SimpleCV image.
        
        """
        
        if(self.image == None):
            array = np.fromstring(self.imageData['data'],dtype='uint8')
            array = array.reshape(self.imageData['width'],self.imageData['height'],3)
            array = np.swapaxes(array,0,1)
            self.image = Image(array)
        return self.image
            
    def handle_mousePosition(self, data):
        if self._position is not None:
            pos = self._clamp(self._mouseOffset(self._position))
        else:
            pos = None
        self.connection.send(pos)

    def handle_mousePositionRaw(self,data):
        self.connection.send(self._position)

