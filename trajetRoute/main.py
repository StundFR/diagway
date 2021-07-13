def _start_end_points(layer, output_path):
    processing.run("qgis:extractspecificvertices", {"INPUT" : layer, "VERTICES" : "0, -1", "OUTPUT" : output_path})

def _add_coordinates_points(layer, output_path):
    processing.run("qgis:exportaddgeometrycolumns", {"INPUT" : layer, "CALC_METHOD" : 0, "OUTPUT" : output_path})

def _shortest_path(layer, pos_start, pos_end):
    vectorLayer = layer
    director = QgsVectorLayerDirector(vectorLayer, -1, '', '', '', QgsVectorLayerDirector.DirectionBoth)
    strategy = QgsNetworkDistanceStrategy()
    director.addStrategy(strategy)

    builder = QgsGraphBuilder(vectorLayer.sourceCrs())

    startPoint = pos_start
    endPoint = pos_end

    tiedPoints = director.makeGraph(builder, [startPoint, endPoint])
    tStart, tStop = tiedPoints

    graph = builder.graph()
    idxStart = graph.findVertex(tStart)
    idxEnd = graph.findVertex(tStop)

    (tree, costs) = QgsGraphAnalyzer.dijkstra(graph, idxStart, 0)

    if tree[idxEnd] == -1:
        raise Exception('No route!')

    # Total cost
    cost = costs[idxEnd]

    # Add last point
    route = [graph.vertex(idxEnd).point()]

    # Iterate the graph
    while idxEnd != idxStart:
        idxEnd = graph.edge(tree[idxEnd]).fromVertex()
        route.insert(0, graph.vertex(idxEnd).point())
    
    layer = QgsVectorLayer("LineString?crs=epsg:32718", "shortest_path", "memory")
    layer.startEditing()

    feature = QgsFeature()
    line = QgsGeometry.fromPolylineXY(route)
    feature.setGeometry(line)

    layer.addFeature(feature)
    layer.commitChanges()

    return layer


project = QgsProject.instance()
layer = project.mapLayersByName("route_client")[0]
layer.setSubsetString("gid = 1")

output_path = "P:/QuentinCochet/Plugin/trajetRoute/tmp/testaaa.shp"
vertices = _start_end_points(layer, output_path)
vertices = QgsVectorLayer(output_path, "", "ogr")

output_path = "P:/QuentinCochet/Plugin/trajetRoute/tmp/test2aaa.shp"
vertices_coord = _add_coordinates_points(vertices, output_path)
vertices_coord = QgsVectorLayer(output_path, "", "ogr")

pos = []
feats = vertices_coord.getFeatures()
for f in feats:
    pos.append([f["xcoord"], f["ycoord"]])

pos_start = QgsPointXY(pos[0][0], pos[0][1])
pos_end = QgsPointXY(pos[1][0], pos[1][1])

path = _shortest_path(layer, pos_start, pos_end)

project.addMapLayer(path)