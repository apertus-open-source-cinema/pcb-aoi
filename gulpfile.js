const gulp = require('gulp')
const nodemon = require('gulp-nodemon')
const browserSync = require('browser-sync').create()
var reload = browserSync.reload

gulp.task('nodemon', function (cb) {
  var callbackCalled = false
  return nodemon({script: './index.js'}).on('start', function () {
    if (!callbackCalled) {
      callbackCalled = true
      cb()
    }
  })
})

gulp.task('connect', function () {
  browserSync.init(null, {
    proxy: {
      target: 'http://localhost:8080',
      ws: true
    }
  })

  gulp.watch(['./app/**', './*.js'], reload) // ['html'])
})

gulp.task('default', ['connect', 'nodemon'])
