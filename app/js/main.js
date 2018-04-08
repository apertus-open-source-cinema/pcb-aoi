var socketio = io()
var socket = socketio.connect('http://localhost:8080')

function start () {
  socket.on('news', function (data) {
    console.log(data)
    socketio.emit('my other event', { my: 'data' })
  })

  socket.on('image', function (data) {
    console.log(data)
    var outputArea = document.getElementById('output-content')
    outputArea.src = 'data:image/png;base64,' + data.buffer

    // socketio.emit('my other event', { my: 'data' })
  })
}

function handleDrop (e) {
  console.log('Drop executed')

  // Stops default drop action, like loading file content.
  e.preventDefault()
  e.stopPropagation()

  console.log('File name: ' + e.dataTransfer.files[0].name)

  var uploader = new SocketIOFileClient(socket)
  uploader.on('start', function (fileInfo) {
    console.log('Start uploading', fileInfo)
  })
  uploader.on('stream', function (fileInfo) {
    console.log('Streaming... sent ' + fileInfo.sent + ' bytes.')
  })
  uploader.on('complete', function (fileInfo) {
    console.log('Upload Complete', fileInfo)
    e.dataTransfer.items.clear()
  })
  uploader.on('error', function (err) {
    console.log('Error!', err)
  })
  uploader.on('abort', function (fileInfo) {
    console.log('Aborted: ', fileInfo)
  })
  var files = e.dataTransfer.files
  uploader.on('ready', function (fileInfo) {
    uploader.upload(files)
  })

  document.getElementById('preview-content').src = window.URL.createObjectURL(e.dataTransfer.files[0])

  var dropArea = document.getElementById('drop-area')
  dropArea.classList.remove('drop-area-hover')

  return false
}

window.onload = function () {
  start()

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

  //   dropArea.addEventListener('dragend', function (e) {
  //     e.preventDefault()
  //     dropArea.classList.remove('drop-area-hover')
  //   })

  dropArea.addEventListener('drop', handleDrop)
}
