import json
from typing import Annotated
import osmnx as ox
import pandas as pd
from fastapi import APIRouter, Query, Body, Depends
from shapely import Polygon
import networkx as nx
import numpy as np
import scipy as sp
import math
# import geopandas as gd

# import app.public_transport_osmnx.osmnx as ox
from app.database import driver, create_graph, get_graph, check_graph, remove_graph

router = APIRouter(
    prefix="/network",
    tags=["Network"],
)



async def filter_parameters(bus: bool = False, tram: bool = False, trolleybus: bool = False, subway: bool = False):
    result = []

    if bus:
        result.append("bus")

    if tram:
        result.append("tram")

    if trolleybus:
        result.append("trolleybus")

    if subway:
        result.append("subway")

    return result


FilterParams = Annotated[dict, Depends(filter_parameters)]


def get_nodes_percentage(valid_bus_node, nodes_list):
    if len(nodes_list) == 0: return 0
    count = 0
    for x in nodes_list:
        if x in valid_bus_node:
            count += 1
    return int(count / len(nodes_list) * 100)

def remove_nodes_cluster(valid_bus_node, nodes_list):
    for x in nodes_list:
        if x in valid_bus_node:
            valid_bus_node[x] = False

def same_transport(node1, node2):
    # if node1['bus'] != node2['bus'] or node1['tram'] != node2['tram'] or node1['subway'] != node2['subway'] or node1['trolleybus'] != node2['trolleybus']:
    if node1['bus'] != node2['bus'] or node1['tram'] != node2['tram']:
        return False
    return True

def get_city_name_data(city_name: str, filters):
    city_polygon = ox.geocoder.geocode_to_gdf(city_name).geometry.iloc[0]
    return get_city_polygon_data(city_polygon, filters)

def get_city_polygon_data(city_polygon, transport_filter):

    if city_polygon.geom_type == "MultiPolygon":
        coords = []
        for polygon in city_polygon.geoms:
            coords.extend([f"{lat} {lon}" for lon, lat in polygon.exterior.coords])
        coords = " ".join(coords)
        # coords = " ".join(f"{lat} {lon}" for lon, lat in list(city_polygon.geoms)[0].exterior.coords)
    elif city_polygon.geom_type == "Polygon":
        coords = " ".join(f"{lat} {lon}" for lon, lat in city_polygon.exterior.coords)
    else:
        raise "ERROR POLYGON"

        
    routes_filter = ''
    for x in transport_filter:
        routes_filter += x + '|'
    if len(routes_filter) > 0 : 
        routes_filter = routes_filter[:-1]
    else: 
        raise "tranpost filter is empty"


    
    nodes_overpass_query = f"""
    [out:json];
    (
      node["public_transport"="stop_position"](poly:"{coords}");
    );
    out body;
    >;
    out skel qt;
    """
    routes_overpass_query = f"""
        [out:json];
        relation["route"~"{routes_filter}"](poly:"{coords}")->.routes;
        (
          .routes;
        );
        out body;
        >;
        out skel qt;
        """

    ways_overpass_query = f"""
    [out:json];
        relation["route"~"{routes_filter}"](poly:"{coords}")->.routes;
        way(r.routes);  // добавляем запрос для всех ways маршрута
        (
          //.routes;
          way(r.routes);  // добавляем way в выходной набор
        );
        out body geom;  // используем 'geom' для получения геометрии
        >;
        out skel qt;

    """


    nodes_response = ox._overpass._overpass_request(data={"data": nodes_overpass_query})
    routes = ox._overpass._overpass_request(data={"data": routes_overpass_query})
    ways_info = ox._overpass._overpass_request(data={"data": ways_overpass_query})

    return (nodes_response, routes, ways_info)
    
def get_bbox_data(bounds, transport_filter):
    south = bounds[0]
    west = bounds[1]
    north = bounds[2]
    east = bounds[3]

    routes_filter = ''
    for x in transport_filter:
        routes_filter += x + '|'
    if len(routes_filter) > 0 : 
        routes_filter = routes_filter[:-1]
    else: 
        raise "transport filter is empty"


    nodes_overpass_query = f"""
    [out:json];
    node["public_transport"="stop_position"]({south},{west},{north},{east})->.nodes;
    (
        .nodes;
    );
    out body;
    >;
    out skel qt;
    """

    routes_overpass_query = f"""
    [out:json];
    relation["route"~"{routes_filter}"]({south},{west},{north},{east})->.routes;
    (
      .routes;
    );
    out body;
    >;
    out skel qt;
    """

    ways_overpass_query = f"""
    [out:json];
    relation["route"~"{routes_filter}"]({south},{west},{north},{east})->.routes;
    way(r.routes);  // добавляем запрос для всех ways маршрута
    ( 
        way(r.routes);  // добавляем way в выходной набор
    );
    out body geom;  // используем 'geom' для получения геометрии
    >;
    out skel qt;
    """

    nodes_response = ox._overpass._overpass_request(data={"data": nodes_overpass_query})
    routes = ox._overpass._overpass_request(data={"data": routes_overpass_query})
    ways_info = ox._overpass._overpass_request(data={"data": ways_overpass_query})

    return (nodes_response, routes, ways_info)

def make_nodes_dataframe(nodes_response):
    nodes_list = []
    for row in nodes_response['elements']:
        tmp_dict = row['tags']
        tmp_dict['osmid'] = row['id']
        tmp_dict['x'] = row['lat']
        tmp_dict['y'] = row['lon']
        nodes_list.append(tmp_dict)
    nodes_df = pd.DataFrame.from_dict(nodes_list)
    nodes_df = nodes_df.replace({np.nan: None})

    return nodes_df

def transport_filter_nodes(nodes_df: pd.DataFrame, filters) -> list:
    nodes = []
    for idx, row in nodes_df.iterrows():
        if 'bus' in nodes_df and row['bus'] == "yes" and 'bus' in filters:
            nodes.append(row)
        elif 'tram' in nodes_df and row['tram'] == "yes" and 'tram' in filters:
            nodes.append(row)                                                                                                   
        elif 'subway' in nodes_df and row['subway'] == "yes" and 'subway' in filters:
            nodes.append(row)
        elif 'trolleybus' in nodes_df and row['trolleybus'] == "yes" and 'trolleybus' in filters:
            nodes.append(row)

    return nodes

def inside_bound_filter_nodes(routes, nodes, percentage_bound=100) -> tuple:

    valid_bus_node = {}
    for x in nodes:
        valid_bus_node[x['osmid']] = True

    relations = pd.DataFrame(columns=['relation_id', 'relation_name','relation_members', 'relation_ways'])

    for element in routes["elements"]:
        if element['type'] != 'relation':
            continue

        node_list = []
        way_list = []

        for member in element['members']:
            if (member['type'] == 'node' and "stop" in member['role']):
                node_list.append(member['ref'])
            elif (member['type'] == 'way'):
                way_list.append(member['ref'])

        if get_nodes_percentage(valid_bus_node, node_list) < percentage_bound:
            remove_nodes_cluster(valid_bus_node, node_list)
            continue

        relations.loc[len(relations)] = [element['id'], element['tags']['name'], node_list, way_list]

    return (valid_bus_node, relations)

def insert_cluster_node_graph(graph, nodes, valid_bus_node, max_dist=200):
    nodes = sorted(nodes, key=lambda x: (str(x['name']), x['x'], x['y']))
    tmp_node = nodes[0]
    if not valid_bus_node[tmp_node['osmid']]:
        for x in nodes:
            if valid_bus_node[x['osmid']]:
                tmp_node = x
                break
    cluster = [[tmp_node.to_dict()]]
    node_cluster = {tmp_node['osmid']: 0}
    j = 0
    for i in range(1, len(nodes)):
        # if node_cluster[nodes[i]['osmid']] == -1 or node_cluster[tmp_node['osmid']] == -1: continue
        if not valid_bus_node[nodes[i]['osmid']]: continue
        if nodes[i]['name'] == tmp_node['name'] and math.dist([tmp_node['x'], tmp_node['y']], [nodes[i]['x'],nodes[i]['y']]) * 111000 < max_dist and same_transport(tmp_node, nodes[i]):
            cluster[j].append(nodes[i].to_dict())
        else:
            j += 1
            cluster.append([nodes[i].to_dict()])
            # cluster.append([nodes[i]['osmid']])
        node_cluster[nodes[i]['osmid']] = j
        tmp_node = nodes[i]
    for cl in cluster:
        bus = "no"
        tram = "no"
        subway = "no"
        trolleybus = "no"
        transport = ""
        if 'bus' in cl[0] and cl[0]['bus'] == "yes":
            transport += " Автобус"
            bus = "yes"
        if 'tram' in cl[0] and cl[0]['tram'] == "yes":
            transport += " Трамвай"
            tram = "yes"
        if 'subway' in cl[0] and cl[0]['subway'] == "yes":
            transport += " Метро"
            subway = "yes"
        if 'trolleybus' in cl[0] and cl[0]['trolleybus'] == "yes":
            transport += " Троллейбус"
            trolleybus = "yes"
        if transport == "": tranposrt = " "
        graph.add_node(cl[0]['osmid'], x=cl[0]['x'], y=cl[0]['y'], name=cl[0]['name'], transport=transport[1:], stops_osmid=[i['osmid'] for i in cl])
        # print(graph.nodes(data=True))
    # print(graph.nodes)
    return (node_cluster, cluster)

def insert_cluster_edge_graph(graph, relations, valid_bus_node, node_cluster, cluster):

    relation_names = {}

    for idx, row in relations.iterrows():
        members = row['relation_members']
        l = -1
        for i in range(len(members)):
            if members[i] in node_cluster and valid_bus_node[members[i]]:
                l = i
                break
        if l == -1: continue

        r = l + 1
        while r < len(members):
            if members[r] in node_cluster and valid_bus_node[members[r]] and valid_bus_node[members[l]]:
                fst = cluster[node_cluster[members[l]]][0]['osmid']
                snd = cluster[node_cluster[members[r]]][0]['osmid']
                if node_cluster[members[l]] != node_cluster[members[r]] and fst in graph.nodes and snd in graph.nodes:
                    # print(fst)
                    graph.add_edge(fst, snd, length=math.dist([graph.nodes[fst]['x'], graph.nodes[fst]['y']],
                                                          [graph.nodes[snd]['x'], graph.nodes[snd]['y']]) * 111000)
                
                if (fst, snd) not in relation_names:
                    relation_names[(fst, snd)] = {'relations' : []}
                if row['relation_name'] not in relation_names[(fst, snd)]:
                    relation_names[(fst, snd)]['relations'].append(row['relation_name'])
                l = r
            r += 1
    nx.set_edge_attributes(graph, relation_names)
    # print(graph.edges.data(True))
    # print(relation_names)
        
    


@router.get("/name")
async def network_by_name(
        city: Annotated[str, Query(description="Название города.")],
        connected: Annotated[
            bool, Query(description="Нужно ли соединять остановки разных типов транспорта в радиусе 200 метров.")],
        filters: FilterParams
):
    """
    Возвращает сеть общественного транспорта по названию.
    """

    geocode_gdf = ox.geocode_to_gdf(city)
    boundaries = geocode_gdf["geometry"]
    pd.set_option('display.max_columns', None)
    nodes_response, routes, ways_info = get_city_name_data(city, filters)
    nodes_df = make_nodes_dataframe(nodes_response)
    nodes = transport_filter_nodes(nodes_df, filters)
    
    # nodes.sort(key=lambda x: (str(x['name']), x['x'], x['y']))

    G = nx.Graph()  # создаем пустой граф
    if "crs" not in G.graph:
        G.graph["crs"] = "EPSG:4326"  # задаем параметр для работы с координатами


    # way_nodes = {}
    # way_geometry = {}
    # for element in ways_info['elements']:
    #     if element['type'] == "way":
    #         way_nodes[element['id']] = element['nodes']
    #         way_geometry[element['id']] = element['geometry']
    # # print(way_nodes)

    valid_bus_node, relations = inside_bound_filter_nodes(routes, nodes)
    node_cluster, cluster = insert_cluster_node_graph(G, nodes, valid_bus_node)
    insert_cluster_edge_graph(G, relations, valid_bus_node, node_cluster, cluster)


    # print(G.nodes)
    G = nx.MultiGraph(G)
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    characters = (list(nx.degree_centrality(G).items()))
    characters1 = (list(nx.closeness_centrality(G).items()))
    characters2 = (list(nx.betweenness_centrality(G).items()))
    characters3 = (list(nx.pagerank(G, alpha=0.85).items()))
    i = 0
    for idx, row in gdf_nodes.iterrows():
        stop_id = idx
        # print(idx)
        # row["osmid"] = idx
        row["center_count"] = characters[i][1]
        row["closeness_centrality"] = characters1[i][1]
        row["betweenness_centrality"] = characters2[i][1]
        row["pagerank"] = characters3[i][1]
        i = i + 1
        G.add_node(stop_id, **row.to_dict())

    
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    df_center = geocode_gdf[["lat", "lon"]]
    data = {
        "center": [geocode_gdf.loc[0, "lon"], geocode_gdf.loc[0, "lat"]],
        "boundaries": json.loads(boundaries.to_json()),
        "nodes": json.loads(gdf_nodes.to_json()),
        # "nodes": gdf_nodes.to_json(),
        "edges": json.loads(gdf_relationships.to_json()),
    }
    create_graph(driver, df_center, gdf_nodes, gdf_relationships)
    # print(data)
    return json.dumps(data)


@router.get("/bbox")
async def network_by_bbox(
        north: Annotated[float, Query(description="Северная широта ограничительной рамки.")],
        south: Annotated[float, Query(description="Южная широта ограничительной рамки.")],
        east: Annotated[float, Query(description="Восточная долгота ограничивающей рамки.")],
        west: Annotated[float, Query(description="Западная долгота ограничивающей рамки.")],
        connected: Annotated[
            bool, Query(description="Нужно ли соединять остановки разных типов транспорта в радиусе 200 метров.")],
        filters: FilterParams
):
    """
   Возвращает сеть общественного транспорта по ограниченой рамке.
    """

    nodes_response, routes, ways_info = get_bbox_data([south, west, north, east], filters)
    nodes_df = make_nodes_dataframe(nodes_response)
    nodes = transport_filter_nodes(nodes_df, filters)
    G = nx.Graph()  # создаем пустой граф
    if "crs" not in G.graph:
        G.graph["crs"] = "EPSG:4326"  # задаем параметр для работы с координатами
    valid_bus_node, relations = inside_bound_filter_nodes(routes, nodes, percentage_bound=50)
    node_cluster, cluster = insert_cluster_node_graph(G, nodes, valid_bus_node)
    insert_cluster_edge_graph(G, relations, valid_bus_node, node_cluster, cluster)
    print(G)
    


    # G, routes, stops, paths_routes = ox.graph_from_bbox(north, south, east, west, simplify=True, retain_all=True,
    #                                                     network_types=filters, connected=connected)
    G = nx.MultiGraph(G)
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    characters = (list(nx.degree_centrality(G).items()))
    characters1 = (list(nx.closeness_centrality(G).items()))
    characters2 = (list(nx.betweenness_centrality(G).items()))
    characters3 = (list(nx.pagerank(G, alpha=0.85).items()))
    i = 0
    for idx, row in gdf_nodes.iterrows():
        stop_id = idx
        # print(idx)
        # row["osmid"] = idx
        row["center_count"] = characters[i][1]
        row["closeness_centrality"] = characters1[i][1]
        row["betweenness_centrality"] = characters2[i][1]
        row["pagerank"] = characters3[i][1]
        i = i + 1
        G.add_node(stop_id, **row.to_dict())
    
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    df_center = pd.DataFrame(data={"lon": (east + west) / 2, "lat": (north + south) / 2}, index=[0, ])
    data = {
        "center": [(east + west) / 2, (north + south) / 2],
        "nodes": json.loads(gdf_nodes.to_json()),
        "edges": json.loads(gdf_relationships.to_json()),
    }
    create_graph(driver, df_center, gdf_nodes, gdf_relationships)
    return json.dumps(data)


@router.post("/polygon")
async def network_by_polygon(
        polygon: Annotated[
            list[tuple[float, float]], Body(description="Последовательность координат, задающая полигон.")],
        connected: Annotated[
            bool, Query(description="Нужно ли соединять остановки разных типов транспорта в радиусе 200 метров.")],
        filters: FilterParams
):
    """
   Возвращает сеть общественного транспорта по полигону.
    """
    print(Polygon(polygon))
    nodes_response, routes, ways_info = get_city_polygon_data(Polygon(polygon), filters)
    nodes_df = make_nodes_dataframe(nodes_response)
    nodes = transport_filter_nodes(nodes_df, filters)
    G = nx.Graph()  # создаем пустой граф
    if "crs" not in G.graph:
        G.graph["crs"] = "EPSG:4326"  # задаем параметр для работы с координатами
    valid_bus_node, relations = inside_bound_filter_nodes(routes, nodes, percentage_bound=50)
    node_cluster, cluster = insert_cluster_node_graph(G, nodes, valid_bus_node)
    insert_cluster_edge_graph(G, relations, valid_bus_node, node_cluster, cluster)
    print(G)
    


    # G, routes, stops, paths_routes = ox.graph_from_bbox(north, south, east, west, simplify=True, retain_all=True,
    #                                                     network_types=filters, connected=connected)
    G = nx.MultiGraph(G)
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    characters = (list(nx.degree_centrality(G).items()))
    characters1 = (list(nx.closeness_centrality(G).items()))
    characters2 = (list(nx.betweenness_centrality(G).items()))
    characters3 = (list(nx.pagerank(G, alpha=0.85).items()))
    i = 0
    for idx, row in gdf_nodes.iterrows():
        stop_id = idx
        # print(idx)
        # row["osmid"] = idx
        row["center_count"] = characters[i][1]
        row["closeness_centrality"] = characters1[i][1]
        row["betweenness_centrality"] = characters2[i][1]
        row["pagerank"] = characters3[i][1]
        i = i + 1
        G.add_node(stop_id, **row.to_dict())
    
    gdf_nodes, gdf_relationships = ox.graph_to_gdfs(G)
    polygon = Polygon(polygon)
    center = list(polygon.centroid.coords[0])
    print(center)
    df_center = pd.DataFrame(data = {"lon": center[0], "lat": center[1]}, index=[0, ])
    data = {
        "center": [df_center.loc[0, "lon"], df_center.loc[0, "lat"]],
        "nodes": json.loads(gdf_nodes.to_json()),
        "edges": json.loads(gdf_relationships.to_json()),
    }
    create_graph(driver, df_center, gdf_nodes, gdf_relationships)
    return json.dumps(data)


@router.get("/db/check")
async def is_graph_exist():
    """
    Проверяет существует ли граф в базе данных.
    """
    return {"is_graph_exist": bool(check_graph(driver))}


@router.post("/db")
async def read_graph(
        polygon: Annotated[
            list[tuple[float, float]], Body(description="Последовательность координат, задающая полигон.")] = None
):
    """
    Возвращает граф из базы данных.
    """
    df_center, gdf_nodes, gdf_relationships = get_graph(driver, polygon)
    data = {
        "center": [df_center.loc[0, "lon"], df_center.loc[0, "lat"]],
        "nodes": json.loads(gdf_nodes.to_json()),
        "edges": json.loads(gdf_relationships.to_json()),
    }
    return json.dumps(data)

@router.get("/db/delete")
async def delete_graph():
    """
    Удаляет граф из базы данных.
    """
    remove_graph(driver)

@router.get("/test")
async def get_test_string():
    data = {"message": "Hello from backend!"}
    return json.dumps(data)


'''
from fastapi import HTTPException
import json


@router.post("/test")
async def post_test_data(data: dict):  # 修改为接受字典类型
    """
    处理POST请求，接收前端发送的数据并进行处理。
    """
    if not data:
        raise HTTPException(status_code=400, detail="No data received")

    features_list = data['nodes']['features']
    center_count = [feature['properties']['center_count'] for feature in features_list]

    # 返回响应给前端
    return {"status": "success", "received_data": center_count}  # 直接返回数据
'''
from fastapi import HTTPException, Response
import io
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# 幂律分布函数
def power_law(x, alpha):
    return x**(-alpha)

# 绘制分布图和拟合结果的函数
def plot_power_law(values, fit_params):
    values = np.array(values)
    # 对数据进行排序（如果未排序）
    values_sorted = np.sort(values)
    # 计算累积分布函数（CDF）的值，用于绘制
    cdf_values = np.arange(1, len(values_sorted) + 1) / len(values_sorted)
    # 绘制原始数据的CDF
    plt.plot(values_sorted, cdf_values, 'o', label='Original Data CDF')
    # 绘制拟合的幂律分布CDF（需要对PDF进行积分得到CDF的近似）
    fit_x = np.linspace(min(values_sorted), max(values_sorted), 1000)
    fit_y = (fit_x**(-fit_params[0])) / (fit_params[0] * min(values_sorted)**(1 - fit_params[0]))
    fit_y_cdf = np.cumsum(fit_y) / np.sum(fit_y)  # 归一化积分得到CDF
    plt.plot(fit_x, fit_y_cdf, '-', label=f'Power Law Fit: α={fit_params[0]:.2f}')
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel('PageRank')
    plt.ylabel('Cumulative Distribution Function')
    plt.legend()
    plt.title('PageRank Distribution and Power Law Fit')

    # 将图像保存到内存中而不是磁盘
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()  # 关闭图形，防止占用内存
    img.seek(0)  # 回到开始位置
    return img

@router.post("/test")
async def post_test_data(data: dict):  # 修改为接受字典类型
    """
    处理POST请求，接收前端发送的数据并进行处理。
    """
    if not data or 'nodes' not in data:
        raise HTTPException(status_code=400, detail="No valid data received")

    features_list = data['nodes']['features']
    pagerank = [feature['properties']['pagerank'] for feature in features_list]

    if len(pagerank) == 0:
        raise HTTPException(status_code=400, detail="No pagerank data available")

    # 拟合幂律分布
    params, _ = curve_fit(power_law, np.arange(1, len(pagerank) + 1), sorted(pagerank, reverse=True), p0=[1])

    # 生成图像
    image = plot_power_law(pagerank, params)

    return Response(content=image.getvalue(), media_type="image/png")