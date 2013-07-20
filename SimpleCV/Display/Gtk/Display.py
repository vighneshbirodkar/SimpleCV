from ..Base import Display
from ..Base.Display import DisplayBase
from ..Base import Line
from ..Base import DisplayNotFoundException
from Worker import GtkWorker
from multiprocessing import Pipe


class GtkDisplay(Display.DisplayBase):
    """
    A Display for SimpleCV using Gtk back-end. Each GtkDisplay spawns a GtkWorker,
    which is a seperate process do display images passed to it. GtkDisplay itself
    doesn't do gtk calls. It send messages to the Worker to tell it what to do
    
    Images may have non-empty Drawing layers. Each layer may have shapes.
    These are communicated to the GtkWorker via the send_* calls
    eg. A Line is handled by the send_Line call.
    
    """
    
    def name(self): 
        __doc__ = DisplayBase.name.__doc__
        return "GtkDisplay"
        
    def __init__(self,size = (640,480),type_ = Display.DEFAULT,title = "SimpleCV",fit = Display.SCROLL):
        
        DisplayBase.__init__(self,size,type_,title,fit)
        parentConnection,childConnnection = Pipe()
        
        self.type_ = type_
        self.fit = fit
        self.imageWidgetSize = None
        
        #Initializing a Worker, A process to handle one display
        
        #create and start the worker process
        self.worker = GtkWorker(childConnnection,size,type_,title,fit)
        self.connection = parentConnection
        self.worker.start()
        
        #whether or not the chil process is alive
        self.workerAlive= True
        self.imageWidgetSize = self.getImageWidgetSize()
        
        
    def close(self):
        __doc__ = DisplayBase.close.__doc__
        
        #terminate the worker process
        self.worker.terminate()
        
    def _checkIfWorkerDead(self):
        """
        
        **SUMMARY**
        
        Checks if the Worker process has requested to be killed. Sets the
        workerAlive flag
        
        """
        if(self.connection.poll()):
            if(self.connection.recv() == 'Kill Me' ):
                print "rec"
                # " Hasta La Vista , Baby "
                # http://www.youtube.com/watch?v=DMGh82QHVcQ
                self.worker.terminate()
                self.workerAlive = False
                
    def getImageWidgetSize(self):
        """
        
        **SUMMARY**
        
        Get the size allocated to the image widger in the Display
        
        **RETURNS**
        
        A (width,height) tuple
        
        """
        
        self._checkIfWorkerDead()
        
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'getImageWidgetSize'
            self.connection.send(dic)
            return self.connection.recv()
        else:
            raise DisplayNotFoundException(self)
    
    def showImage(self,img):
        self._checkIfWorkerDead()
               
        if(self.workerAlive):
            # Converts the image to a string and passes it in a dict along
            # with other necessary info. This is more efficient than sending
            # the whole image
            
            dic = {}
            dic['function'] = 'showImage'
            dic['data'] = img.toString()
            dic['depth'] = img.depth
            dic['width'] = img.width
            dic['height'] = img.height
            dic['layers'] = img.layers()
            self.connection.send(dic)
            
        else:
            raise DisplayNotFoundException(self)
            


    @property
    def mouseX(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'mouseX'
            self.connection.send(dic)
            return self.connection.recv()[0]

    @property
    def mouseY(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'mouseY'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def leftDown(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'leftButtonDownPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def rightDown(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'rightButtonDownPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def leftUp(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'leftButtonUpPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def rightUp(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'rightButtonUpPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def middleDown(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'middleButtonDownPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def middleUp(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'middleButtonUpPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def mouseScrollPosition(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'mouseScrollPosition'
            self.connection.send(dic)
            return self.connection.recv()[0]

    def mouseScrollType(self):
        if(self.workerAlive):
            dic = {}
            dic['function'] = 'mouseScrollType'
            self.connection.send(dic)
            return self.connection.recv()[0]


