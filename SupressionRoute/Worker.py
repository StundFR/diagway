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

    def __init__(self, items, source_layer, field):
        QtCore.QObject.__init__(self)
        self.items = items
        self.source_layer = source_layer
        self.field = field
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
    def getRoadsDone(self, destination_layer, output_path):
        temp_path = tempfile.gettempdir()
        dir_path = temp_path + "/SupressionRouteTmpLayer"
        createDir(dir_path)

        source_layer = self.source_layer
        field = self.field
        extract = []

        ids = getAllFeatures(destination_layer, field)
        ids = supprDouble(ids)
        length = len(ids)

        if (not destination_layer.isLT93()):
            destination_layer = destination_layer.projectionLT93("{}/{}_LT93.shp".format(dir_path, destination_layer.name))

        progress_count = 0
        self.progress.emit(0)

        for i in ids:
            if self.killed:
                self.progress.emit(100)
                return None

            buffer_path = "{}\\buffer_{}.shp".format(dir_path, str(progress_count))
            extract_path = "{}\\extract_{}.shp".format(dir_path, str(progress_count))

            destination_layer.filter("{} = {}".format(field, i))

            buffer = destination_layer.buffer(50, buffer_path)

            extractByLocation(source_layer, buffer, extract_path)

            extract.append(QgsLayer(extract_path, str(progress_count)).vector)

            progress_count += 1
            self.progress.emit((progress_count / length)*100)

        mergeLayers(extract, output_path)

        return QgsLayer(output_path, "RoadsDone")

    #Create layer with all the road not recorded yet
    def getRoadsUndone(self, destination_layer, output_path):
        temp_path = tempfile.gettempdir()
        dir_path = temp_path + "/SupressionRouteTmpLayer"
        createDir(dir_path)

        source_layer = self.source_layer
        self.progress.emit(0)

        if (self.killed):
            return

        output_buffer = "{}\\{}_buffer.shp".format(dir_path, destination_layer.name)
        if (not destination_layer.isLT93()):
            destination_layer = destination_layer.projectionLT93("{}\\{}_LT93.shp".format(dir_path, destination_layer.name))
        destination_layer = destination_layer.buffer(1, output_buffer)

        if (self.killed):
            return

        self.progress.emit(40)

        difference(source_layer.vector, destination_layer.vector, output_path)

        if (self.killed):
            return

        self.progress.emit(100)

        return QgsLayer(output_path, "RoadsUndone")
    #--------------------------------------------------------------------------
    
    """Run"""
    def run(self):
        try:
            temp_path = tempfile.gettempdir()
            dir_path = temp_path + "/SupressionRouteTmpLayer"
            createDir(dir_path)

            output_path = "{}\\merged.shp".format(dir_path)
            self.mergedSelectLayers(output_path)

            destination_layer = QgsLayer(output_path, "")
            output_path = "{}\\getRoadsDone.shp".format(dir_path)
            destination_layer = self.getRoadsDone(destination_layer, output_path)

            output_path = "{}\\getRoadsUndone.shp".format(dir_path)
            layer = self.getRoadsUndone(destination_layer, output_path)
        except Exception as e:
            layer = None
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(layer)
