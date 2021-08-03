from PyQt5 import QtCore
from PyQt5.QtGui import QColor
from .Layer import QgsLayer
from .Tools import *
import traceback

LAYER_STATEMENT_NAME = "Statement_source"

class WorkerAuto(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(str, str, str)
    error = QtCore.pyqtSignal(Exception, str)

    def __init__(self, layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision):
        QtCore.QObject.__init__(self)
        self.layer_source = layer_source
        self.layer_dest = layer_dest
        self.source_value = source_value
        self.field_source = field_source
        self.field_dest = field_dest
        self.buffer_distance = buffer_distance
        self.precision = precision
    #--------------------------------------------------------------------------

    """Function for the algorithm"""

    #--------------------------------------------------------------------------
    
    """Run"""
    def run(self):
        try:
            dest_value = projection(self.layer_source, self.layer_dest, self.source_value, self.field_source, self.field_dest, self.buffer_distance, self.precision)

            #Create the line wich be put in the lineEdit
            line = ""
            print(dest_value)
            for value in dest_value:
                line += str(value) + ";"
            line = line[:-1]
            print(line)

            #Create expression for rules styles
            expression_dest = expressionFromFields(self.field_dest, line)
            expression_source = expressionFromFields(self.field_source, self.source_value)

            destination_rules = (
                ("Destinations", expression_dest, QColor(65,105,225)), #Blue
                ("Other", "ELSE", QColor(139,69,19)) #Brown
            )
            source_rules = (
                ("source", expression_source, QColor(255,215,0)), #Gold
                ("Other", "ELSE", QColor("orange"))
            )

            self.layer_dest.styleByRules(destination_rules)
            self.layer_source.styleByRules(source_rules)

            #Filter the layer for the zoom at the end
            self.layer_source.filter(expression_source)

            layer_statement = QgsLayer.findLayerByName(LAYER_STATEMENT_NAME)
            layer_statement.setVisibility(False)
            self.layer_source.setVisibility(True)
            self.layer_dest.setVisibility(True)
            
        except Exception as e:
            line = ""
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(line, expression_source, expression_dest)
