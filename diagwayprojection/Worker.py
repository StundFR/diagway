from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback

class Worker(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(QgsLayer)
    error = QtCore.pyqtSignal(Exception, str)
    progress = QtCore.pyqtSignal(float)

    def __init__(self, source_layer, destination_layer, csv_path, source_field, destination_field):
        QtCore.QObject.__init__(self)
        self.source_layer = source_layer
        self.destination_layer = destination_layer
        self.csv_path = csv_path
        self.source_field = source_field
        self.destination_field = destination_field
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

            with open(self.csv_path, "r") as csv:
                csv_lines = csv.readlines()

            for line in csv_lines:
                source_values_done.append(line.split(";")[0])
            source_values_done.pop(0)

            source_feats = self.source_layer.getFeatures()
            for feat in source_feats:
                source_values.append(str(feat[self.source_field]))

            source_values_toDo = [source_value for source_value in source_values if source_value not in source_values_done]

            length = len(source_values_toDo)
            
            count_progress = 1
            for source_value in  source_values_toDo:
                if (self.killed):
                    statementSource_layer = None
                    break

                if (source_value is str):
                    self.source_layer.filter("{} = '{}'".format(self.source_field, source_value))
                else:
                    self.source_layer.filter("{} = {}".format(self.source_field, source_value))

                destination_values = getDestBySource(self.source_layer, self.destination_layer, source_value, self.source_field, self.destination_field, 50)

                if (len(destination_values) > 0):
                    line = ""
                    for dest_value in destination_values:
                        line += str(dest_value) + ";"
                    line = line[:-1]

                    addLineCSV(self.csv_path, source_value, line)

                    count_progress += 1
                    self.progress.emit(count_progress*100/length)

            self.source_layer.setVisibility(False)
            self.destination_layer.setVisibility(False)

            statementSource_layer, statementDestination_layer = createLayerStyleByCSV(self.csv_path)

            #Clear filter 
            self.source_layer.filter("")
            self.destination_layer.filter("")
        except Exception as e:
            statementSource_layer = None
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(statementSource_layer)
