from PyQt5 import QtCore
from .Layer import QgsLayer
from .Tools import *
import traceback
import psycopg2
import csv


SCHEMA = "cores"
SOURCE = "stc_voie"
DEST = "route_client"
FIELD_SOURCE = "sta_id"
FIELD_DEST = "route_client"

class WorkerDistance(QtCore.QObject):
    """Constructor & Variables"""
    finished = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal(Exception, str)

    def __init__(self, database, host, user, password, port, regenerate, add, layer_source, layer_dest, path_csv, field_source, field_dest, fields_source, fields_dest):
        QtCore.QObject.__init__(self)
        self.database = database
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.regenerate = regenerate
        self.add = add
        self.layer_source = layer_source
        self.layer_dest = layer_dest
        self.path_csv = path_csv
        self.field_source = field_source
        self.field_dest = field_dest
        self.fields_source = fields_source
        self.fields_dest = fields_dest
        self.killed = False
    #--------------------------------------------------------------------------

    """Function for the algorithm"""
    #--------------------------------------------------------------------------

    """Run"""
    def run(self):
        try:
            self.layer_source.name = self.layer_source.name.lower().replace(".", "")
            self.layer_dest.name = self.layer_dest.name.lower().replace(".", "")

            #Add to database to Qgis
            addPostgisDB(self.host, self.database, self.user, self.password, self.port)

            # Open connection
            conn = psycopg2.connect(host=self.host, dbname=self.database, user=self.user, password=self.password, port=self.port)
            cur = conn.cursor()


            if self.regenerate:
                """
                Création/Remplacement de toutes les données
                """
                """Création des nouvelles tables"""
                sqlQuery = "SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{}'".format(SCHEMA)
                cur.execute(sqlQuery)
                res = len(cur.fetchall())

                if res == 1:
                    sqlQuery = "ALTER SCHEMA {schema} RENAME TO {schema}_backup".format(schema = SCHEMA)
                    cur.execute(sqlQuery)
                    conn.commit()

                strSqlQuery = "CREATE SCHEMA IF NOT EXISTS {}".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "DROP TABLE IF EXISTS {}.terrain_client".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE {}.terrain_client (troncon_id integer, route_client text, cumuld_client numeric, cumulf_client numeric)".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "DROP TABLE IF EXISTS {}.client_terrain".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE {}.client_terrain (gid serial,route_client text,type_troncon text,geom_client geometry(LineStringM,2154),point_deb_client geometry(PointM,2154),point_fin_client geometry(PointM,2154),longueur_client numeric,troncon_id integer,cumuld_troncon numeric,cumulf_troncon numeric,longueur_terrain numeric,ecart numeric, sens_ausc integer, a_verifier boolean,CONSTRAINT client_terrain_pkey PRIMARY KEY (gid))".format(SCHEMA)
                cur.execute(strSqlQuery)

                """Importation des couches depuis QGIS avec uniquement les colonnes selectionées"""
                self.layer_source.exportToPostgisLineString(self.database, self.host, SCHEMA, SOURCE, "geom")
                self.layer_dest.exportToPostgisLineString(self.database, self.host, SCHEMA, DEST, "geom")

                table_tuple = [(SOURCE, self.fields_source, self.field_source, FIELD_SOURCE), (DEST, self.fields_dest, self.field_dest, FIELD_DEST)]

                for tuple in table_tuple:
                    sqlQuery = "SELECT column_name FROM information_schema.columns WHERE table_schema = '{}' AND table_name = '{}'".format(SCHEMA, tuple[0])
                    cur.execute(sqlQuery)

                    columns = cur.fetchall()
                    for elem in columns:
                        if not elem[0] in tuple[1] and elem[0] != "geom" and elem[0] != tuple[2]: 
                            sqlQuery = "ALTER TABLE {}.{} DROP COLUMN {}".format(SCHEMA, tuple[0], elem[0])
                            cur.execute(sqlQuery)

                    if tuple[2] != tuple[3]:
                        sqlQuery = "ALTER TABLE {}.{} RENAME COLUMN {} TO {}".format(SCHEMA, tuple[0], tuple[2], tuple[3])
                        cur.execute(sqlQuery)

                conn.commit()

                """Importation des données du fichier CSV dans la BDD"""
                strSqlQueryInsertTerrainClient = "INSERT INTO {}.terrain_client (troncon_id,route_client) VALUES(%s,%s)".format(SCHEMA)
                strstrSqlQueryInsertClientTerrain = "INSERT INTO {}.client_terrain (route_client,troncon_id) VALUES(%s,%s)".format(SCHEMA)

                with open(self.path_csv, newline='') as csvfile:
                    reader = csv.DictReader(csvfile,delimiter=';')
                    reader = csv.DictReader(csvfile,delimiter=';')
                    for row in reader:
                        sta_id=row[self.field_source]
                        for route_client in (row[self.field_dest]).split(";"):
                            cur.execute(strSqlQueryInsertTerrainClient,(sta_id,route_client))
                            cur.execute(strstrSqlQueryInsertClientTerrain,(route_client,sta_id))            
                    conn.commit()
                
                """Calcul des distances"""
                strSqlQuery = "UPDATE {}.client_terrain set type_troncon='Route'".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "UPDATE {schema}.client_terrain t1 set longueur_client = ST_LENGTH(t2.geom) from {schema}.{dest} t2 where t1.route_client = t2.route_client".format(schema = SCHEMA, dest = DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {schema}.client_terrain t1 set geom_client = t2.geom from {schema}.{dest} t2 where t1.route_client = t2.route_client".format(schema = SCHEMA, dest = DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {}.client_terrain set point_deb_client = ST_StartPoint(geom_client),point_fin_client = ST_EndPoint(geom_client)".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()
                
                strSqlQuery = "alter table {}.client_terrain add column geom_terrain geometry(MultiLineStringM,2154)".format(SCHEMA)
                cur.execute(strSqlQuery)
                ########################################################################################################################
            elif self.add:
                """
                Ajout de nouvelles correspondances ou données sans modifier ce qui à déjà été fait
                """
                """On remplace les anciens couches par les nouvelles de QGIS en gardant les mêmes colonnes que précédemment"""
                sqlQuery = "ALTER TABLE {}.{} RENAME TO tmp_source".format(SCHEMA, SOURCE)
                cur.execute(sqlQuery)

                sqlQuery = "ALTER TABLE {}.{} RENAME TO tmp_dest".format(SCHEMA, DEST)
                cur.execute(sqlQuery)

                conn.commit()

                self.layer_source.exportToPostgisLineString(self.database, self.host, SCHEMA, SOURCE, "geom")
                self.layer_dest.exportToPostgisLineString(self.database, self.host, SCHEMA, DEST, "geom")

                conn.commit()

                table_tuple = [(SOURCE, "tmp_source", self.field_source, FIELD_SOURCE), (DEST, "tmp_dest", self.field_dest, FIELD_DEST)]

                for tuple in table_tuple:
                    sqlQuery = "SELECT column_name FROM information_schema.columns WHERE table_schema = '{}' AND table_name = '{}'".format(SCHEMA, tuple[1])
                    cur.execute(sqlQuery)
                    columns_keep = cur.fetchall()

                    sqlQuery = "SELECT column_name FROM information_schema.columns WHERE table_schema = '{}' AND table_name = '{}'".format(SCHEMA, tuple[0])
                    cur.execute(sqlQuery)
                    columns = cur.fetchall()

                    for elem in columns:
                        if not elem[0] in columns_keep and elem[0] != "geom" and elem[0] != tuple[2]: 
                            sqlQuery = "ALTER TABLE {}.{} DROP COLUMN {}".format(SCHEMA, tuple[0], elem[0])
                            cur.execute(sqlQuery)

                    if tuple[2] != tuple[3]:
                        sqlQuery = "ALTER TABLE {}.{} RENAME COLUMN {} TO {}".format(SCHEMA, tuple[0], tuple[2], tuple[3])
                        cur.execute(sqlQuery)

                    sqlQuery = "DROP TABLE {}.{} CASCADE".format(SCHEMA, tuple[1])
                    cur.execute(sqlQuery)

                conn.commit()

                """Creation des tables avec les nouvelles correspondance"""
                strSqlQuery = "CREATE TABLE {}.new_terrain_client (troncon_id integer, route_client text, cumuld_client numeric, cumulf_client numeric)".format(SCHEMA)
                cur.execute(strSqlQuery)
                
                strSqlQuery = "CREATE TABLE {}.new_client_terrain (gid serial, route_client text, type_troncon text, geom_client geometry(LineStringM,2154), point_deb_client geometry(PointM,2154), point_fin_client geometry(PointM,2154), longueur_client numeric, troncon_id integer, cumuld_troncon numeric, cumulf_troncon numeric, longueur_terrain numeric, ecart numeric, sens_ausc integer, a_verifier boolean, geom_terrain geometry(MultiLineStringM,2154), CONSTRAINT new_client_terrain_pkey PRIMARY KEY (gid))".format(SCHEMA)
                cur.execute(strSqlQuery)

                strSqlQueryInsertTerrainClient = "INSERT INTO {}.new_terrain_client (troncon_id,route_client) VALUES(%s,%s)".format(SCHEMA)
                strstrSqlQueryInsertClientTerrain = "INSERT INTO {}.new_client_terrain (route_client,troncon_id) VALUES(%s,%s)".format(SCHEMA)

                with open(self.path_csv, newline='') as csvfile:
                    reader = csv.DictReader(csvfile,delimiter=';')
                    reader = csv.DictReader(csvfile,delimiter=';')
                    for row in reader:
                        sta_id=row[self.field_source]
                        for route_client in (row[self.field_dest]).split(";"):
                            cur.execute(strSqlQueryInsertTerrainClient,(sta_id,route_client))
                            cur.execute(strstrSqlQueryInsertClientTerrain,(route_client,sta_id))   

                    conn.commit()

                """Toutes les correspondances qui n'ont pas été modifié ne sont pas recalculer"""
                sqlQuery = "UPDATE {schema}.new_terrain_client t1 SET cumuld_client = t2.cumuld_client, cumulf_client = t2.cumulf_client FROM {schema}.terrain_client t2 WHERE t1.troncon_id = t2.troncon_id AND t1.route_client = t2.route_client".format(schema = SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "UPDATE {schema}.new_client_terrain t1 SET type_troncon = t2.type_troncon, geom_client = t2.geom_client, point_deb_client = t2.point_deb_client, point_fin_client = t2.point_fin_client, longueur_client = t2.longueur_client, cumuld_troncon = t2.cumuld_troncon, cumulf_troncon = t2.cumulf_troncon, longueur_terrain = t2.longueur_terrain, ecart = t2.ecart, sens_ausc = t2.sens_ausc, a_verifier = t2.a_verifier, geom_terrain = t2.geom_terrain FROM {schema}.client_terrain t2 WHERE t1.troncon_id = t2.troncon_id AND t1.route_client = t2.route_client".format(schema = SCHEMA)
                cur.execute(sqlQuery)

                conn.commit()

                """Récupération des nouvelles correspondance à calculer"""
                sqlQuery = "CREATE TABLE {schema}.calcul_client_terrain AS (SELECT * FROM {schema}.new_client_terrain EXCEPT SELECT * FROM {schema}.client_terrain)".format(schema = SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "DELETE FROM {}.new_client_terrain WHERE longueur_terrain IS NULL".format(SCHEMA)
                cur.execute(sqlQuery)

                conn.commit()

                """Calcul sur les nouvelles correspondances"""
                strSqlQuery = "UPDATE {}.calcul_client_terrain set type_troncon='Route'".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "UPDATE {schema}.calcul_client_terrain t1 set longueur_client = ST_LENGTH(t2.geom) from {schema}.{dest} t2 where t1.route_client = t2.route_client".format(schema = SCHEMA, dest = DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {schema}.calcul_client_terrain t1 set geom_client = t2.geom from {schema}.{dest} t2 where t1.route_client = t2.route_client".format(schema = SCHEMA, dest = DEST)
                cur.execute(strSqlQuery)
                conn.commit()

                strSqlQuery = "Update {}.calcul_client_terrain set point_deb_client = ST_StartPoint(geom_client),point_fin_client = ST_EndPoint(geom_client)".format(SCHEMA)
                cur.execute(strSqlQuery)
                conn.commit()

                """Supression de l'ancienne client_terrain et terrain_client"""
                sqlQuery = "DROP TABLE IF EXISTS {}.terrain_client CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE IF EXISTS {}.client_terrain CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)

                conn.commit()

                """Création des nouvelles tables terrain_client et client_terrain"""
                sqlQuery = "CREATE TABLE {schema}.client_terrain AS (SELECT * FROM {schema}.new_client_terrain UNION SELECT * FROM {schema}.calcul_client_terrain)".format(schema = SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "ALTER TABLE {}.client_terrain ADD CONSTRAINT client_terrain_pkey PRIMARY KEY (gid)".format(SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "ALTER TABLE {}.new_terrain_client RENAME TO terrain_client".format(SCHEMA)
                cur.execute(sqlQuery)

                conn.commit()

                """Suppression des tables temporaires"""
                sqlQuery = "DROP TABLE IF EXISTS {}.new_client_terrain CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)

                sqlQuery = "DROP TABLE IF EXISTS {}.calcul_client_terrain CASCADE".format(SCHEMA)
                cur.execute(sqlQuery)

                conn.commit()
                 
            """Calcul des distance"""
            strSqlQuery = "Update {schema}.client_terrain t3 set cumuld_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_deb_client))), cumulf_troncon = ST_M(ST_LineInterpolatePoint(geom_troncon,ST_LineLocatePoint(geom_troncon,point_fin_client))) from (select t1.route_client,t1.geom_client,t1.troncon_id,t2.geom as geom_troncon from {schema}.client_terrain t1 join {schema}.{source} t2 on t1.troncon_id = t2.sta_id ) r1 where t3.route_client = r1.route_client and t3.troncon_id = r1.troncon_id".format(schema = SCHEMA, source = SOURCE)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set longueur_terrain = abs(cumulf_troncon-cumuld_troncon)".format(SCHEMA)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set sens_ausc = CASE When  cumulf_troncon-cumuld_troncon>=0 Then 1 else -1 End".format(SCHEMA)
            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain set ecart = (longueur_terrain-longueur_client)".format(SCHEMA)
            cur.execute(strSqlQuery)

            strSqlQuery = "Update {}.client_terrain set a_verifier = CASE WHEN abs(longueur_terrain-longueur_client)>=10 then TRUE ELSE FALSE END".format(SCHEMA)

            cur.execute(strSqlQuery)
            conn.commit()

            strSqlQuery = "Update {}.client_terrain t1 set geom_terrain = ST_LocateBetween(t2.geom, cumuld_troncon, cumulf_troncon) from {}.{} t2 where t1.troncon_id = t2.sta_id AND GeometryType(t2.geom)=' LINESTRING'".format(SCHEMA, SCHEMA, SOURCE)
            cur.execute(strSqlQuery)
            conn.commit()
                    
            conn.close()
            nb = 1
        except Exception as e:
            nb = 0
            self.error.emit(e, traceback.format_exc())
            
        self.finished.emit(nb)
