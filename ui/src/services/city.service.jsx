import axios from "axios"
import { BASE_URL } from ".."


export const cityService = {
    async getCity(cityName, transport, connected) {
        console.log('response = ', `http://localhost:80/network/name?city=${cityName}&connected=${connected}&bus=${transport.bus}&tram=${transport.tram}&trolleybus=${transport.trolleybus}`);
        const response = await axios.get(`http://localhost:80/network/name?city=${cityName}&connected=${connected}&bus=${transport.bus}&tram=${transport.tram}&trolleybus=${transport.trolleybus}&subway=${transport.subway}`, {withCredentials: true});
        return JSON.parse(response.data);
    },
    async getBbox(bbox, transport, connected) {
        console.log('bb = ', bbox);
        console.log('url = ', BASE_URL + `/network/bbox?connected=${connected}&north=${bbox.north}&south=${bbox.south}&east=${bbox.east}&west=${bbox.west}&bus=${transport.bus}&tram=${transport.tram}&trolleybus=${transport.trolleybus}`);
        const response = await axios.get(BASE_URL + `/network/bbox?connected=${connected}&north=${bbox.north}&south=${bbox.south}&east=${bbox.east}&west=${bbox.west}&bus=${transport.bus}&tram=${transport.tram}&trolleybus=${transport.trolleybus}&subway=${transport.subway}`);
        return JSON.parse(response.data);
    },
    // (37.558093;55.780142) (37.664573;55.724120) (37.584589;55.732905)
    async getPolygon(polygon, transport, connected) {
        const response = await axios.post(BASE_URL + `/network/polygon?connected=${connected}&bus=${transport.bus}&tram=${transport.tram}&trolleybus=${transport.trolleybus}&subway=${transport.subway}`, polygon, {headers: {"Content-Type": "application/json"}, withCredentials: true});
        return JSON.parse(response.data);
    }, 
    async dbCheck() {
        const response = await axios.get('http://localhost:80/network/db/check');
        return response.data;
    },
    async getDb() {
        const response = await axios.post('http://localhost:80/network/db');
        return JSON.parse(response.data);
    },
    async deleteGraph() {
        const response = await axios.get('http://localhost:80/network/db/delete');
        return response.data;
    },
    async userDb(positions) {
        const response = await axios.post('http://localhost:80/network/db', positions);
        return JSON.parse(response.data);
    },
    /*
    async sendPowerData(data) {
        try {
            // 发送POST请求，并携带数据
            const response = await axios.post('http://localhost:80/network/test', data);
            // 直接使用response.data，不再需要JSON.parse
            console.log('Server responded with:', response.data);
            return response.data;  // 返回解析后的响应数据
        } catch (error) {
            console.error('Error sending data:', error.response ? error.response.data : error.message);
            throw error; // 重新抛出异常以便上层处理
        }
    },*/
    async sendPowerData(data) {
        try {
            // 发送POST请求，并携带数据，指定响应类型为blob以处理二进制数据（如图像）
            const response = await axios.post('http://localhost:80/network/test', data, { responseType: 'blob' });
    
            // 打印响应头内容
            console.log('Response Headers:', JSON.stringify(response.headers));
    
            // 打印响应数据的前几个字节，用于调试
            const reader = new FileReader();
            reader.onloadend = () => {
                console.log('First few bytes of response data:', reader.result.slice(0, 50)); // 打印前50个字节
            };
            reader.readAsText(new Blob([response.data], { type: 'text/plain' }).slice(0, 50));
    
            if (response.headers['content-type'] === 'image/png') {
                const blob = new Blob([response.data], { type: 'image/png' });
                const imageUrl = URL.createObjectURL(blob);
                return imageUrl;
            } else {
                console.error('Unexpected content type:', response.headers['content-type']);
                return null; // 或者其他适当的错误处理
            }
        } catch (error) {
            console.error('Error sending data:', error.response ? error.response.data : error.message);
            throw error; // 重新抛出异常以便上层处理
        }
    },
    async test() {
        const response = await axios.get('http://localhost:80/network/test');
        return JSON.parse(response.data);
    }
}