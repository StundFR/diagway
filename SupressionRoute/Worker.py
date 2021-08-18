from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback
import tempfile

class Worker(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(QgsLayer)
    error = QtCore.pyqtSignal(Exception, str)
    progress = QtCore.pyqtSignal(float)

    def __init__(self, items, layer_source, field, distance, precision):
        QtCore.QObject.__init__(self)
        self.items = items
        self.layer_source = layer_source
        self.field = field
        self.distance = distance
        self.precison = precision
        self.killed = False
    #--------------------------------------------------------------------------

    """Function for the algorithm"""
    def kill(self):
        self.killed = True

    #Merge selected layers
    def mergedSelectLayers(self, output):
        items = self.items
        layers = []
        progress_count = 0
        length = len(items)
        self.progress.emit(0)
        for i in items:
            if (self.killed):
                break

            layer = QgsLayer.findLayerByName(i.text())
            layers.append(layer.vector)
            progress_count += 1
            self.progress.emit((progress_count / length)*100)
        mergeLayers(layers, output)

    #Create layer with all the road already recorded
    def getRoadsUndone(self, layer_dest, path_output):
        path_temp = tempfile.gettempdir()
        path_dir = getPath()
        createDir(path_dir)

        dest_values = []

        ids = layer_dest.getAllFeatures(self.field)
        ids = supprDouble(ids)
        length = len(ids)

        statement = self.layer_source.clone()
        statement.setName("Statement")
        statement.addUniqueID()
        field_source = "newID"

        if (not layer_dest.isLT93()):
            layer_dest = layer_dest.projectionLT93("{}/{}_LT93.shp".format(path_dir, layer_dest.name))

        progress_count = 0
        self.progress.emit(0)

        for i in ids:
            if self.killed:
                self.progress.emit(100)
                break

            dest_values += projection(layer_dest, statement, i, self.field, field_source, self.distance, self.precison)

            progress_count += 1
            self.progress.emit(progress_count*100/length)

        line = ""
        for value in dest_values:
            line += "{};".format(value)
        line = line[:-1]

        expression = expressionFromFields(field_source, line)
        statement.selectByExpression(expression)
        feats = statement.selectedFeatures()

        statement.removeFeaturesByExpression(expression)

        statement.export(path_output)
    #--------------------------------------------------------------------------
    
    """Run"""
    def run(self):
        try:
            path_dir = getPath()
            removeDir(path_dir)
            createDir(path_dir)

            path_output = "{}\\merged.shp".format(path_dir)
            self.mergedSelectLayers(path_output)

            layer_dest = QgsLayer(path_output, "")
            path_output = "{}\\getRoadsUndone.shp".format(path_dir)
            self.getRoadsUndone(layer_dest, path_output)
            layer = QgsLayer(path_output, "Statement")
        except Exception as e:
            layer = None
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(layer)
