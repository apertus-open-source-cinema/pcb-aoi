
var webSocket = new WebSocket('ws://localhost:8081')
var bson = new BSON()

// function start () {
//   // Get the Long type
//   var Long = BSON.Long
//   // Create a bson parser instance
//   var bson = new BSON()

//   // Serialize document
//   var doc = { long: Long.fromNumber(100) }

//   // Serialize a document
//   var data = bson.serialize(doc)
//   bson.serialize("Test", "TestABC")
//   // De serialize it again
//   var doc_2 = bson.deserialize(data)
// }

webSocket.onopen = function () {
  // webS<ocket.send('Test ABC 123')
}

webSocket.onmessage = function (event) {
  console.log(event.data)
}
function handleDrop (e) {
  console.log('Drop executed')

  // Stops default drop action, like loading file content.
  e.preventDefault()
  if (e.stopPropagation) {
    e.stopPropagation()
  }

  var data = {}
  data.name = 'Test123'
  data.test2 = 123 // e.target.files[0].name
  data.fileName = e.dataTransfer.files[0].name
  data.fileData = new Uint8Array(e.dataTransfer.files[0])
  webSocket.binaryType = 'blob'
  var serializedData = bson.serialize(data)
  webSocket.send(serializedData)

  var dropArea = document.getElementById('drop-area')
  dropArea.classList.remove('drop-area-hover')

  return false
}

window.onload = function () {
//   start()

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
