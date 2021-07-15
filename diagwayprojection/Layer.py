from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsWkbTypes, QgsProject

class QgsLayer:
    def __init__(self, path=None, name=None, vectorLayer=None) -> None:
        if (vectorLayer is None):
            self.path = path
            self.name = name
            self.vector = QgsVectorLayer(path, name, "ogr")
            self.crs = self.vector.crs().authid()
        else:
            self.vector = vectorLayer
            self.name = self.vector.name()
            self.path = self.vector.dataProvider().dataSourceUri().split("|")[0]
            self.crs = self.vector.crs().authid()

    def getFields(self):
        fields_list = []
        layer_fields = self.vector.fields()
        for f in layer_fields:
            fields_list.append(f.name())
        return fields_list

    def typeOfField(self, field_name):
        feats = self.vector.getFeatures()
        for feat in feats:
            return type(feat[field_name])

    def zoom(self, layer):
        canvas = self.iface.mapCanvas()
        canvas.setExtent(layer.extent())

    def buffer(self, buffer_distance, buffer_path):
        source_layer_feats = self.vector.getFeatures()
        source_layer_fields = self.vector.fields()
        buffer_name = "{}_buffer".format(self.name)
        writer = QgsVectorFileWriter(buffer_path, 'UTF-8',  source_layer_fields, QgsWkbTypes.Polygon, self.vector.sourceCrs(), 'ESRI Shapefile')
        for feat in source_layer_feats:
            geom = feat.geometry()
            buffer = geom.buffer(buffer_distance, 5)
            feat.setGeometry(buffer)
            writer.addFeature(feat)
        del(writer)
        return QgsLayer(buffer_path, buffer_name)

    def refresh(self):
        self.vector.setDataSource(self.path, self.name, "ogr")

    def add(self):
        layer = QgsProject.instance().addMapLayer(self.vector)
        self.id = layer.id()
        
    def remove(self):
        QgsProject.instance().removeMapLayers([self.id])

    def clone(self):
        name = self.name + "_clone"
        return QgsLayer(self.path, name)

    def setVisibility(self, visibility):
        QgsProject.instance().layerTreeRoot().findLayer(self.id).setItemVisibilityChecked(visibility)

    def isLT93(self):
        return (self.crs == "EPSG:2154")

    def filter(self, expression):
        return self.vector.setSubsetString(expression)

    def getFeatures(self):
        return self.vector.getFeatures()
