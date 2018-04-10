var socketio = io()
var socket = socketio.connect(window.location.hostname + ':8080')
const uploader = new SocketIOFileUpload(socket)

function start () {
  socket.on('image', function (data) {
    var outputArea = document.getElementById('output-content')
    outputArea.src = 'data:image/png;base64,' + data.buffer

    // socketio.emit('my other event', { my: 'data' })
  })

  uploader.listenOnDrop(document.getElementById('drop-area'))

  uploader.addEventListener('progress', function (event) {
    var percent = event.bytesLoaded / event.file.size * 100
    console.log('File is', percent.toFixed(2), 'percent loaded')
  })
}

function handleDrop (e) {
  // Stops default drop action, like loading file content.
  e.preventDefault()
  e.stopPropagation()

  for (var index = 0; index < e.dataTransfer.files.length; index++) {
    console.log('File: ' + e.dataTransfer.files[index].name)
  }

  console.log('File name: ' + e.dataTransfer.files[0].name)

  document.getElementById('preview-content').src = window.URL.createObjectURL(e.dataTransfer.files[0])

  var dropArea = document.getElementById('drop-area')
  dropArea.classList.remove('drop-area-hover')

  return false
}

function setupFileDrop () {
  var dropArea = document.getElementById('drop-area')
  console.log(dropArea)

  dropArea.addEventListener('dragover', function (e) {
    e.preventDefault()
    dropArea.classList.add('drop-area-hover')
  })

  dropArea.addEventListener('dragenter', function (e) {
    e.preventDefault()
    dropArea.classList.add('drop-area-hover')
  })

  dropArea.addEventListener('dragleave', function (e) {
    e.preventDefault()
    dropArea.classList.remove('drop-area-hover')
  })

  dropArea.addEventListener('drop', handleDrop)
}

window.onload = function () {
  start()

  setupFileDrop()
}
