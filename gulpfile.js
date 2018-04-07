const gulp = require('gulp')
const nodemon = require('gulp-nodemon')
const browserSync = require('browser-sync').create()

gulp.task('serve', function () {})

gulp.task('watch', function () {})
gulp.task('nodemon', function () {
  var stream = nodemon({ script: 'index.js',
    ext: 'html js',
    ignore: ['ignored.js'] })

  stream
    .on('restart', function () {
      console.log('restarted!')
    })
    .on('crash', function () {
      console.error('Application has crashed!\n')
      stream.emit('restart', 3) // restart the server in 3 seconds
    })
})

gulp.task('html', function (done) {
  return gulp.src('./app/*.html')
    .pipe(gulp.dest('./app'))
    .pipe(browserSync.stream())
})

gulp.task('connect', function () {
  browserSync.init({
    server: {
      baseDir: './app'
    }
  })

  gulp.watch(['./app/**', './*.js'], ['html'])
})

gulp.task('default', ['connect', 'nodemon', 'watch'])

// const gulp = require('gulp')

// gulp.task('connect', function () {
//   browserSync.init({
//     server: {
//       baseDir: './app'
//     }
//   })

//   gulp.watch(['./app/**'], ['html'])
// })

// gulp.task('html', function (done) {
//   return gulp.src('./app/*.html')
//     .pipe(gulp.dest('./app'))
//     .pipe(browserSync.stream())
// })

// gulp.task('default', ['connect'])
