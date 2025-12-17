import cv2

class RobotCamera:
    def __init__(self, usb_port):
        self.usb_port = usb_port
        self.capture = cv2.VideoCapture(usb_port)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def release(self):
        self.capture.release()
        
    def reopen(self):
        self.capture.open(self.usb_port)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)