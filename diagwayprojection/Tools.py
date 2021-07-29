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
        #print("Directory already exists")
        pass


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
    path_dir = getPath()

    source = str(source_value).replace("/", "")
    path_buffer = path_dir +"/getDestBySource_buffer_{}_{}.shp".format(layer_source.name, source)
    path_extract = path_dir +"/getDestBySource_extract_{}_{}.shp".format(layer_source.name, source)
    path_dissolve = path_dir +"/getDestBySource_dissolve_{}_{}.shp".format(layer_source.name, source)

    if (type(source_value) is str):
        expression = "\"{}\" = '{}'".format(field_source, source_value)
    else:
        expression = "\"{}\" = {}".format(field_source, source_value)

    if not layer_source.filter(expression):
        return []

    layer_buffer = layer_source.buffer(buffer_distance, path_buffer)

    #Check length of buffer
    layer_buffer_feats = layer_buffer.getFeatures()
    count = 0
    for feat in layer_buffer_feats:
        count += 1

    #We need to dissolve buffer if there are more than one features
    if (count > 1):
        #Dissolve
        processing.run('qgis:dissolve', {'INPUT' : path_buffer, 'FIELD' : "stc_route_sta_id", 'OUTPUT' : path_dissolve}) #A corriger pour le rendre dynamique
        #Spatial extract
        intersect(layer_dest, QgsLayer(path_dissolve, ""), precision, path_extract, source_value)
    else:
        #Spatial extract
        intersect(layer_dest, QgsLayer(path_buffer, ""), precision, path_extract, source_value)

    #Get destinations
    layer_res = QgsLayer(path_extract, "res")
    layer_res_feats = layer_res.getFeatures()
    dest_values = []
    for feat in layer_res_feats:
        try:
            dest_values.append(str(feat[field_dest]))
        except KeyError:
            dest_values.append(str(feat[field_dest[:-2]]))

    return dest_values



def getDestByDest(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision, value_already_done):
    path_dir = getPath()

    source = str(source_value).replace("/", "")
    path_buffer = "{}/getDestByDest_buffer_{}_{}.shp".format(path_dir,  layer_dest.name, source)
    layer_buffer_source = layer_source.buffer(buffer_distance, path_buffer)


    path_extract = "{}/getDestByDest_extract_{}_{}.shp".format(path_dir,  layer_dest.name, source)
    extractByLocationIntersect(layer_dest, layer_buffer_source, path_extract)
    layer_extract = QgsLayer(path_extract, "")

    field_values = []
    layer_extract_feats = layer_extract.getFeatures()
    for feat in layer_extract_feats:
        try:
            field_values.append(str(feat[field_dest]))
        except KeyError:
            field_values.append(str(feat[field_dest[:-2]]))

    dest_values = []
    for value in field_values:
        if (str(value) not in value_already_done):
            res_value = getDestBySource(layer_dest, layer_source, value, field_dest, field_source, buffer_distance, precision)
            if (source_value in res_value):
                dest_values.append(value)

    return dest_values


def projection(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision):

    dest_values = getDestBySource(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision)
    dest_values += getDestByDest(layer_source, layer_dest, source_value, field_source, field_dest, buffer_distance, precision, dest_values)
    layer_dest.filter("")

    return supprDouble(dest_values)


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


def intersect(layer_source, layer_dest, precision, path_output, source_value):
    path_dir = getPath()
    alea = int(random()*100/random())

    path_clip = path_dir + "/intersect_clip_{}_{}.shp".format(layer_source.name, source_value)
    clip(layer_source, layer_dest, path_clip)
    layer_clip = QgsLayer(path_clip, "layer_clip")

    path_extract = path_dir + "/intersect_extract_{}_{}.shp".format(layer_source.name, source_value)
    extractByLocationIntersect(layer_source, layer_dest, path_extract)
    layer_extract = QgsLayer(path_extract, "layer_extract")

    layer_clip.addLengthFeat()
    layer_extract.addLengthFeat()

    ids = []
    layer_clip_length = layer_clip.getAllFeatures("newLength")
    layer_extract_length = layer_extract.getAllFeatures("newLength")

    #layer_clip.add()
    #○layer_extract.add()

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


def getPath():
    path_temp = tempfile.gettempdir()
    path_dir = path_temp + "/diagwayProjectionTmpLayer"
    createDir(path_dir)
    return path_dir