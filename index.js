const http = require('http')
const app = require('express')()
const WebSocket = require('ws')
const path = require('path')
var fs = require('fs')
var BSON = require('bson')

const httpPort = 8080

const wss = new WebSocket.Server({port: 8081})

app.get('/', (request, response) => {
  response.sendFile(path.join(__dirname, '/app/index.html'))
})

wss.on('connection', function connection (ws) {
  ws.on('message', function incoming (message) {
    // if (typeof message !== 'string') {
    // `message` is either a `Buffer` or an `ArrayBuffer`.
    console.log('received: %s', message)
    var bson = new BSON()
    //var data = bson.deserialize(message)
    var messageData = bson.deserialize(message)
    // console.log('received: %s', message.buffer.name)
    // console.log('received: %s', message.fileData)

    fs.writeFileSync('./tmp/' + messageData.fileName, Buffer.from(messageData.fileData))
    // }
  })

  ws.send('something 123')
})

// wss.on('message', function incoming (data) {
//   console.log(data)
//   wss.send('message received')
// })

process.on('uncaughtException', function (err) {
  console.log(err)
})

app.listen(httpPort, (err) => {
  if (err) {
    return console.log('something bad happened', err)
  }

  console.log(`server is listening on ${httpPort}`)
})

// const requestHandler = (request, response) => {
//     console.log(request.url)
//     response.end('Hello Node.js Server!')
// }

// const server = http.createServer(requestHandler)

// server.listen(httpPort, (err) => {
//     if (err) {
//         return console.log('something bad happened', err)
//     }
// })

// http.createServer(function (request, response) {
//     var filePath = '.' + request.url;
//     if (filePath == './')
//         filePath = './app/index.html';
//     //res.writeHead(200, {'Content-Type': 'text/plain'});
//     //res.end('Hello World!');
// }).listen(httpPort);
