const express = require('express');
const os = require('os');
const app = express();
const port = 3000;

function getLocalIP() {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address;
            }
        }
    }
    return 'localhost';
}

app.use(express.static('public'));

app.get('/api/ip', (req, res) => {
    res.json({ ip: getLocalIP() });
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
