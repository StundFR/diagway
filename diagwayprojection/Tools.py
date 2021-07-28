from qgis import processing
from qgis.core import QgsVectorFileWriter
from os import mkdir
import shutil
from random import random
import tempfile

from .Layer import QgsLayer

def supprDouble(list):
    resList = []
    for element in list:
        if element not in resList:
            resList.append(element)
    return resList


def createDir(path_dir):
    try:
        mkdir(path_dir)
    except FileExistsError:
        print("Directory already exists")


def removeDir(path_dir):
    try:
        shutil.rmtree(path_dir)
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))


def getNameFromPath(path):
    name = path.split("/")
    name = name[len(name)-1]
    return name.split(".")[0]


def expressionFromFields(label, line):
    if (type(line.split(";")[0]) is str):
        line = "'" + line.replace(";", "','") + "'"
    else:
        line = line.replace(";", "','")

    return "\"{}\" in ({})".format(label, line)


def duplicateLineCSV(csv_path, source_value):
    i = 0
    with open(csv_path, "r") as csv:
        lines = csv.readlines()
    for line in lines:
        i += 1
        if (line.split(";")[0] == str(source_value)):
            return i
    i = 0
    return i


def removeLineFile(path_file, nLine):
    with open(path_file, "r") as file:
        file_lines = file.readlines()
    
    i = 1
    with open(path_file, "w") as file:
        for line in file_lines:
            if (i != nLine):
                file.write(line)
            i += 1


def extractByLocation(layer_source, layer_dest, path_output):
    parameters = {'INPUT' : layer_source.vector, 'PREDICATE' : 6, 'INTERSECT' : layer_dest.vector, 'OUTPUT' : path_output}
    processing.run("qgis:extractbylocation", parameters)


def getDestBySource(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision):
    #Create folder in temp
    path_temp = tempfile.gettempdir()
    path_dir = path_temp + "/diagwayProjectionTmpLayer"
    createDir(path_dir)

    source = str(source_value)
    source = source.replace("/", "")
    path_buffer = path_dir +"/routeBuffer_" + source + ".shp"
    path_extract = path_dir +"/routeExtract_" + source +".shp"
    path_dissolve = path_dir +"/routeDissolve_" + source +".shp"

    if (type(source_value) is str):
        expression = "\"{}\" = '{}'".format(field_source, source_value)
    else:
        expression = "\"{}\" = {}".format(field_source, source_value)

    if not layer_source.filter(expression):
        return []

    layer_source.buffer(buffer_distance, path_buffer)

    #Check length of buffer
    layer_buffer = QgsLayer(path_buffer, "")
    layer_buffer_feats = layer_buffer.getFeatures()
    count = 0
    for feat in layer_buffer_feats:
        count += 1

    #We need to dissolve buffer if there are more than one features
    if (count > 1):
        #Dissolve
        processing.run('qgis:dissolve', {'INPUT' : path_buffer, 'FIELD' : "stc_route_sta_id", 'OUTPUT' : path_dissolve})
        #Spatial extract
        intersect(layer_dest, QgsLayer(path_dissolve, ""), precision, path_extract)
    else:
        #Spatial extract
        intersect(layer_dest, QgsLayer(path_buffer, ""), precision, path_extract)

    #Get destinations
    layer_res = QgsLayer(path_extract, "res")
    layer_res_feats = layer_res.getFeatures()
    destination_values = []
    for feat in layer_res_feats:
        try:
            destination_values.append(feat[field_dest])
        except KeyError:
            destination_values.append(feat[field_dest[:-2]])


    return destination_values
        

def addLineCSV(csv_path, source_value, destination_value):
    duplicateLine = duplicateLineCSV(csv_path, source_value)

    if (duplicateLine != 0):
        removeLineFile(csv_path, duplicateLine)

    line = "{};\"{}\"\n".format(source_value, destination_value)
    with open(csv_path, "a") as csv:
        csv.write(line)


def createLayerStyleByCSV(csv_path):
    csv_layer = QgsLayer(csv_path, "")
    csv_layer.refresh()

    layer_statement = QgsLayer.findLayerByName("Statement_source")

    QgsLayer.styleByCSV(layer_statement, csv_path)
    layer_statement.setVisibility(True)

    return layer_statement


def mergeLayers(layers, path_output):
    parameters = {'LAYERS': layers, 'CRS': 'EPSG:4326', 'OUTPUT': path_output}
    processing.run("native:mergevectorlayers", parameters) 


def difference(layer_source, layer_dest, path_output):
    parameters = {"INPUT" : layer_source.vector, "OVERLAY" : layer_dest.vector, "OUTPUT" : path_output}
    processing.run("qgis:difference", parameters)


def clip(layer_source, layer_dest, path_output):
    parameters = {"INPUT" : layer_source.vector, "OVERLAY" : layer_dest.vector, "OUTPUT" : path_output}
    processing.run("qgis:clip", parameters)


def extractByLocationIntersect(layer_source, layer_dest, path_output):
    parameters = {'INPUT' : layer_source.vector, 'PREDICATE' : 0, 'INTERSECT' : layer_dest.vector, 'OUTPUT' : path_output}
    processing.run("qgis:extractbylocation", parameters)


def intersect(layer_source, layer_dest, precision, path_output):
    path_temp = tempfile.gettempdir()
    path_dir = path_temp + "/diagwayProjectionTmpLayer"
    createDir(path_dir)
    alea = int(random()*100/random())

    path_clip = path_dir + "/{}_clip_{}.shp".format(layer_source.name, alea)
    clip(layer_source, layer_dest, path_clip)
    layer_clip = QgsLayer(path_clip, "layer_clip")

    path_extract = path_dir + "/{}_extract_{}.shp".format(layer_source.name, alea)
    extractByLocationIntersect(layer_source, layer_dest, path_extract)
    layer_extract = QgsLayer(path_extract, "layer_extract")

    layer_clip.addLengthFeat()
    layer_extract.addLengthFeat()

    ids = []
    layer_clip_length = layer_clip.getAllFeatures("Length")
    layer_extract_length = layer_extract.getAllFeatures("Length")

    for i in range(len(layer_clip_length)):
        if (layer_clip_length[i]/layer_extract_length[i] >= precision):
            ids.append(i)

    layer_extract_feats = layer_extract.getFeatures()

    i = 0
    selection = []
    for feat in layer_extract_feats:
        if (i in ids):
            selection.append(feat)
        i += 1

    layer_extract.vector.selectByIds([s.id() for s in selection])

    writer = QgsVectorFileWriter.writeAsVectorFormat(layer_extract.vector, path_output, "utf-8", layer_extract.vector.sourceCrs(), "ESRI Shapefile", onlySelected=True)
    del(writer)

    return QgsLayer(path_output, "{}_intersect_{}".format(layer_source.name, layer_dest.name))


