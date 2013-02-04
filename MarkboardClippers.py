from Foundation import *
from AppKit import *


class OSXClipObject(object):
    def __init__(self, theData):
        pasteboard = NSPasteboard.generalPasteboard()
        typeArray = NSArray.arrayWithObject_(NSHTMLPboardType)
        pasteboard.declareTypes_owner_(typeArray, None)
        pasteboard.setString_forType_(theData, NSHTMLPboardType)