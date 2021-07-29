from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback

class Worker(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(QgsLayer)
    error = QtCore.pyqtSignal(Exception, str)
    progress = QtCore.pyqtSignal(float)

    def __init__(self, layer_source, layer_dest, path_csv, field_source, field_dest, buffer_distance, precision):
        QtCore.QObject.__init__(self)
        self.layer_source = layer_source
        self.layer_dest = layer_dest
        self.path_csv = path_csv
        self.field_source = field_source
        self.field_dest = field_dest
        self.buffer_distance = buffer_distance
        self.precision = precision
        self.killed = False
    #--------------------------------------------------------------------------

    """Function for the algorithm"""
    def kill(self):
        self.killed = True

    #--------------------------------------------------------------------------
    
    """Run"""
    def run(self):
        try:
            source_values_done = []
            source_values = []

            with open(self.path_csv, "r") as csv:
                csv_lines = csv.readlines()

            for line in csv_lines:
                source_values_done.append(line.split(";")[0])
            source_values_done.pop(0)

            layer_source_feats = self.layer_source.getFeatures()
            for feat in layer_source_feats:
                source_values.append(str(feat[self.field_source]))

            source_values_toDo = [source_value for source_value in source_values if source_value not in source_values_done]

            length = len(source_values_toDo)
            
            count_progress = 0
            self.progress.emit(count_progress*100/length)
            
            for source_value in  source_values_toDo:
                if (self.killed):
                    layer_statement = None
                    break

                destination_values = projection(self.layer_source, self.layer_dest, source_value, self.field_source, self.field_dest, self.buffer_distance, self.precision)

                if (len(destination_values) > 0):
                    line = ""
                    for dest_value in destination_values:
                        line += str(dest_value) + ";"
                    line = line[:-1]

                    addLineCSV(self.path_csv, source_value, line)

                count_progress += 1
                self.progress.emit(count_progress*100/length)

            self.layer_source.setVisibility(False)
            self.layer_dest.setVisibility(False)

            layer_statement = createLayerStyleByCSV(self.path_csv)

            #Clear filter 
            self.layer_source.filter("")
            self.layer_dest.filter("")
        except Exception as e:
            layer_statement = None
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(layer_statement)
