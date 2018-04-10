'use strict'
const express = require('express')
const app = express()
const server = require('http').Server(app)
const io = require('socket.io')(server)
const path = require('path')
// const SocketIOFile = require('socket.io-file')
// const fs = require('fs')
const SocketIOFileUpload = require('socketio-file-upload')
const sharp = require('sharp')
const { execSync } = require('child_process')

const httpPort = 8080

server.listen(httpPort)

app.use(express.static(path.join(__dirname, '/app')))
app.use(SocketIOFileUpload.router)

app.get('/', (request, response) => {
  response.sendFile(path.join(__dirname, '/app/index.html'))
})

io.on('connection', function (socket) {
  console.log('a user connected: ' + socket)

  socket.emit('news', { hello: 'world' })
  socket.on('my other event', function (data) {
    console.log(data)
  })

  const uploader = new SocketIOFileUpload()
  uploader.dir = path.join(__dirname, '/tmp')
  uploader.listen(socket)

  uploader.on('saved', function (event) {
    console.log(event.file)

    var cmd = 'python ./python/pcb_processing.py ' + event.file.pathName
    execSync(cmd, (err, stdout, stderr) => {
      if (err) {
        // node couldn't execute the command
        return
      }

      // the *entire* stdout and stderr (buffered)
      console.log(`stdout: ${stdout}`)
      console.log(`stderr: ${stderr}`)
    })

    // Create thumbnail and push to the page
    // TODO: Replace with something more meaningful
    sharp('./tmp/warp.png')
      .resize(200)
      .toBuffer().then(function (buffer) {
        var base64Buffer = buffer.toString('base64')
        socket.emit('image', { image: true, buffer: base64Buffer })
      })
  })
})
