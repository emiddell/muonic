"""
Provides helper classes and function needed by the gui
"""
from matplotlib.pylab import rc

from PyQt6 import QtGui, QtCore, QtWidgets

class HistoryAwareLineEdit(QtWidgets.QLineEdit):
    """
    A LineEdit widget that is aware of its input history. The history can be
    cycled by pressing arrow up and arrow down.

    :param args: widget args
    """
    def __init__(self, *args):
        QtWidgets.QLineEdit.__init__(self, *args)
        self.history = []
        self.hist_pointer = 0
        
    def event(self, event):
        """
        Handles keypress events.

        :param event: event object
        :returns: bool
        """
        if event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == QtCore.Qt.Key_Down:
                self.emit(QtCore.SIGNAL("keyDownPressed"))
                if self.hist_pointer < len(self.history) - 1:
                    self.hist_pointer += 1
                    self.setText(self.history[self.hist_pointer])
                elif self.hist_pointer == len(self.history) - 1:
                    self.setText('')
                    self.hist_pointer += 1
                return True
            if event.key() == QtCore.Qt.Key_Up:
                self.emit(QtCore.SIGNAL("keyUpPressed"))
                if self.hist_pointer > 0:
                    self.hist_pointer -= 1
                    self.setText(self.history[self.hist_pointer])
                return True
            else:
                return QtWidgets.QLineEdit.event(self, event)
        return QtWidgets.QLineEdit.event(self, event)

    def add_hist_item(self, item):
        """
        Add item to input history.

        :param item: the item to add
        :type item: str
        :returns: None
        """
        self.history.append(item)
        self.hist_pointer = len(self.history)


def set_large_plot_style():
    """
    Large fonts for large screens

    :returns: None
    """
    font_size = 20
    
    ff = "sans"

    rc("axes", titlesize=font_size, labelsize=font_size)
    # rc("font", serif="Palatino")
    rc("font", size=font_size, family=ff)  # this is Palatino
    rc("grid", linewidth=1.2)
    rc("legend", fontsize=font_size, markerscale=1, numpoints=1)
    rc("lines", linewidth=2, markersize=10)
    rc("ps", useafm=True)
    rc("pdf", use14corefonts=True)
    rc("xtick", labelsize=font_size)
    rc("xtick.major", size=7)
    rc("xtick.minor", size=5)
    rc("ytick", labelsize=font_size)
    rc("ytick.major", size=7)
    rc("ytick.minor", size=5)

# vim: ai ts=4 sts=4 et sw=4
