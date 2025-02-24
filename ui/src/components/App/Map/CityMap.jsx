import React, { useState } from "react";
import styles from '../Map/Map.module.css'
import { MapContainer, TileLayer, Polyline, Circle, Polygon, useMapEvents} from 'react-leaflet'
import { Marker, Popup } from "react-leaflet";
import { cityService } from "../../../services/city.service";




function CityMap({tramNodes, tramEdges, busNodes, busEdges, center, subwayEdges, subwayNodes, edges, nodes,max,min,numberСentrality}) {

    function colors(num,x1,x2,x3,x4)
    {
    let x;
    if (Number(num)===1)
    {
        x=x1;
    }
    if (Number(num)===2)
    {
      x=x2;
    }
    if (Number(num)===3)
    {
       x=x3;
    }
    if (Number(num)===4)
    {
       x=x4;
    }        

    
      let  l=0;
      let  r=120;
      let  a=min;
      let  b=max;
      let z= r-(r - l) * (x-a)/(b-a);
        return 'hsl('+z+', 100%, 50%)';
    }

    const tramEdgesOptions = { color: 'red' };
    const tramNodesOptions = { color: 'darkred'};
    const busEdgesOptions = { color: '#0000FF' };
    const busNodesOptions = { color: 'darkblue' };
    const subwayEdgesOptions = { color: 'lime'};
    const subwayNodesOptions = { color: '#304D30'};
    const redOptions = {color: 'black'};
    
    const [tramNodes_, setTramNodes] = useState(tramNodes);
    const [tramEdges_, setTramEdges] = useState(tramEdges);
    const [busNodes_, setBusNodes] = useState(busNodes);
    const [busEdges_, setBusEdges] = useState(busEdges);
    const [subwayNodes_, setSubwayNodes] = useState(subwayNodes);
    const [subwayEdges_, setSubwayEdges] = useState(subwayEdges);
    const [edges_, setEdges] = useState(edges);
    const [nodes_, setNodes] = useState(nodes);
    const [positions, setPositions] = useState([]);

    const [showMap, setShowMap] = useState(true); // 新增：用于控制显示地图还是结点数据
    const toggleView = async () => {
        setShowMap(!showMap);
    };

    function LocationGetter() {
        useMapEvents({
              click(e) {
                  setPositions([...positions, e.latlng]);
              }
        });
        return null;
    }
    function getMaxOfArray(numArray) {
        return Math.max.apply(null, numArray);
      }
      function getMinOfArray(numArray) {
        return Math.min.apply(null, numArray);
      }
    function transportname(id,yes)
    {
        if (id==1 && yes=='yes')
            return 'Автобус';
        if (id==2 && yes=='yes')
            return 'Трамвай';

    }

    function clear() {
        setPositions([]);
    }

    function saveNodes() {
        const nodesData = nodes_;
        const blob = new Blob([JSON.stringify(nodesData)], {type: "application/json"});
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a'); 
        link.download = "nodes.json";
        link.href = url;
        link.click();  
    }

    function saveEdges() {
        const edgesData = edges_;
        const blob = new Blob([JSON.stringify(edgesData)], {type: "application/json"});
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a'); 
        link.download = "edges.json";
        link.href = url;
        link.click();  
    }
    async function polygonHandle() {
        let data = {};
        if (positions.length === 0) {
            data = await cityService.getDb();
        }
        else {
            let userPolygon = positions.map((el) => [el.lng, el.lat]);
            userPolygon.push([positions[0].lng, positions[0].lat]);
            data = await cityService.userDb(userPolygon);
        }
        center = [await data.center[1], await data.center[0]];
        setEdges(data.edges);
        setNodes(data.nodes);

      setBusEdges(data.edges.features.filter((el) => (el)).map(item => [item.geometry.coordinates[0],item.geometry.coordinates[1],item.properties.length] ));
    setBusNodes(await data.nodes.features.filter((el) => (el)).map(item => [item.properties.y, item.properties.x, item.id, item.properties.center_count, item.properties.name, item.properties.bus, item.properties.tram, item.properties.closeness_centrality, item.properties.betweenness_centrality, item.properties.pagerank]));

    }
    /*
    async function handleSendDataButtonClick() {
        try {
            // 调整数据结构以符合后端期望
            const dataToSend = { nodes: nodes_ };
            const responseData = await cityService.sendPowerData(dataToSend);
            
            console.log('Server responded with:', responseData.received_data); // 确认这里是否打印了正确的数据
            
            alert('Data processed successfully!');
            
            // 显示处理后的数据
            document.getElementById('output').textContent = JSON.stringify(responseData.received_data, null, 2) || 'No data received';
        } catch (error) {
            console.error('Error sending data:', error);
            alert('Failed to send data.');
        }
    }*/
    async function handleSendDataButtonClick() {
        try {
            // 调整数据结构以符合后端期望
            const dataToSend = { nodes: nodes_ };
            const imageSrc = await cityService.sendPowerData(dataToSend);

            // 确认这里是否打印了正确的数据
            console.log('Server responded with imageSrc:', imageSrc);

            alert('Data processed successfully!');

            // 显示处理后的数据，如果是图像，则在页面上显示图像
            const outputElement = document.getElementById('output');
            if (typeof imageSrc === 'string' && imageSrc.startsWith('blob:')) {
                outputElement.innerHTML = `<img src="${imageSrc}" alt="Generated Plot" />`;
            } else {
                outputElement.textContent = JSON.stringify(imageSrc, null, 2) || 'No data received';
            }
        } catch (error) {
            console.error('Error sending data:', error);
            alert('Failed to send data.');
        }
    }
    const handleTestButtonClick = async () => {
        try {
            const data = await cityService.test();
            document.getElementById('output').textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            document.getElementById('output').textContent = 'Error fetching data';
        }
    };

    if (showMap) {
        return (         
            <div className={styles.MapContainer}>
                
                <MapContainer className={styles.Map} center={center} zoom={13} scrollWheelZoom={false}>
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    <Marker position={center}>
                        <Popup>
                        Центр города.
    
                        </Popup>
                    </Marker>
                    <LocationGetter/>

                    {/* bus */}
                    {(busEdges_.map((el) =>
                        (
                            
                    <Polyline pathOptions={busEdgesOptions} positions={[el[1],el[0]]}>
                        <Popup>
                        <p>Данные</p>
                    <p>Длинна {el[2]}</p> 
                        </Popup>
                    </Polyline>
                        )
                        ))}
                    {(busNodes_.map((el) =>
                        (
                            <Circle key={el[2]} center={[el[1], el[0]]} radius={20} color={colors(numberСentrality,el[3],el[7],el[8],el[9])} >
                            <Popup>
                            <p>Данные</p>
                            <p>osmid: {el[2]}</p>
                            <p>Наименование: {el[4]}</p>
                            <p>Транспорт: {transportname(1,el[5])} {transportname(2,el[6])}</p>
                            <p>Центральность по степени (degree centrality): {el[3]}</p>
                            <p>Центральность по близости (closeness centrality): {el[7]}</p>
                            <p>Центральность по посредничеству (betweenness centrality): {el[8]}</p>
                            <p>Page Rank: {el[9]}</p>
                            </Popup>
                            </Circle>
                        )
                    ))}
                    {/* tram */}
                    <Polyline pathOptions={tramEdgesOptions} positions={tramEdges_}></Polyline>
                    {(tramNodes_.map((el) =>
                        (
                            <Circle key={el[2]} center={[el[0], el[1]]} radius={10} pathOptions={tramNodesOptions}></Circle>
                        )
                    ))}
                    {/* subway */}
                    <Polyline pathOptions={subwayEdgesOptions} positions={subwayEdges_}></Polyline>
                    {(subwayNodes_.map((el) =>
                        (
                            <Circle key={el[2]} center={[el[0], el[1]]} radius={10} pathOptions={subwayNodesOptions}></Circle>
                        )
                    ))}
                    <Polygon pathOptions={redOptions} positions={positions}></Polygon>
                </MapContainer>
                <button className={styles.btn} onClick={polygonHandle}>Обработать полигон</button>
                <button className={styles.btn} onClick={clear}>Очистить карту</button>
                <button className={styles.btn} onClick={saveNodes}>Сохранить узлы</button>
                <button className={styles.btn} onClick={saveEdges}>Сохранить рёбра</button>
                <button className={styles.btn} onClick={toggleView}>Переключить просмотр</button>
                <div className={styles.legend}>
                    <div className={styles.legendElement}>
                        <hr className={styles.redline}></hr>
                        <span className={styles.objectname}>Трамвайный путь</span>
                    </div>
                    <div className={styles.legendElement}>
                        <div className={styles.redstop}></div>
                        <span className={styles.objectname}>Трамвайная остановка</span>
                    </div>
                    <div className={styles.legendElement}>
                        <hr className={styles.blueline}></hr>
                        <span className={styles.objectname}>Автобусный путь</span>
                    </div>
                    <div className={styles.legendElement}>
                        <div className={styles.bluestop}></div>
                        <span className={styles.objectname}>Автобусная остановка</span>
                    </div>
                    <div className={styles.legendElement}>
                        <hr className={styles.greenline}></hr>
                        <span className={styles.objectname}>Путь метро</span>
                    </div>
                    <div className={styles.legendElement}>
                        <div className={styles.greenstop}></div>
                        <span className={styles.objectname}>Остановка метро</span>
                    </div>
                </div>
            </div>
        )
    }
    else{
        return (
            <div>
                <button className={styles.btn} onClick={toggleView}>Вернуться к карте</button>
                <button className={styles.btn} onClick={handleSendDataButtonClick}>Посмотреть Законы власти</button>
                {/*<button className={styles.btn} onClick={handleTestButtonClick}>testgetdata</button>*/}
                {/* 直接输出返回的数据 */}
                {/* 添加一个空的 div 作为间隔 */}
                <div style={{ height: '20px' }}></div> {/* 调整高度以适应你的需要 */}
                <pre id="output"></pre>
            </div>
        );
    }
}

export default CityMap