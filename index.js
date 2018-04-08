'use strict'
const express = require('express')
const app = express()
var server = require('http').Server(app)
var io = require('socket.io')(server)
const path = require('path')
const SocketIOFile = require('socket.io-file')
var fs = require('fs')

const httpPort = 8080

server.listen(httpPort)

app.use(express.static(path.join(__dirname, '/app')))

app.get('/', (request, response) => {
  response.sendFile(path.join(__dirname, '/app/index.html'))
})

app.get('/socket.io-file-client.js', (req, res, next) => {
  return res.sendFile(path.join(__dirname, '/node_modules/socket.io-file-client/socket.io-file-client.js'))
})

io.on('connection', function (socket) {
  console.log('a user connected: ' + socket)

  socket.emit('news', { hello: 'world' })
  socket.on('my other event', function (data) {
    console.log(data)
  })

  var uploader = new SocketIOFile(socket, {
    uploadDir: 'tmp',
    chunkSize: 102400,
    transmissionDelay: 0,
    overwrite: false
  })

  uploader.on('start', (fileInfo) => {
    console.log('Start uploading')
    console.log(fileInfo)
  })

  uploader.on('complete', (fileInfo) => {
    fs.readFile(path.join(__dirname, fileInfo.uploadDir), function (err, buf) {
      if (err) {
        console.log('Error!', err)
        return
      }

      console.log('Pushing image: ' + fileInfo.name)
      socket.emit('image', { image: true, buffer: buf.toString('base64') })
    })
  })
})
