// -------------------------- VIEW + CONTROLLER -----------------------------

// Display the puzzle in a canvas
// and translate user inputs into model commands
function View() {

  // ------------------ MOUSE CONTROLLER ------------------

  // Convert screen coordinates to board coordinates.
  // Takes into account board translation and zooming.
  // When zoomed-in by 2, a point at 100px from the left of the screen
  // is actually at 50 model-units from it.
  this.toBoardPos = function(pos) {
    var frus = model.frustum;
    var res = {
      x : (pos.x / frus.scale) + frus.x,
      y : (pos.y / frus.scale) + frus.y
    };
    return res;
  }

  // The reverse of above: convert board coords to screen coords.
  this.toScreenPos = function(x, y) {
    var frus = model.frustum;
    var res = {
      x : (x - frus.x) * frus.scale,
      y : (y - frus.y) * frus.scale
    };
    return res;
  }

  // Convert boards dimensions (height, width) into screen dimensions
  this.toScreenDims = function(w, h) {
    var frus = model.frustum;
    var res = {
      w : w * frus.scale,
      h : h * frus.scale
    };
    return res;
  }

  this.toBoardDims = function(w, h) {
    if (!h) // argument missing
      console.log('Warning: toBoardDims requires 2 arguments');
    var frus = model.frustum;
    var res = {
      w : w / frus.scale,
      h : h / frus.scale
    };
    return res;
  }

  this.isMouseDown = false;
  this.dragStart = null; // last position recorded when dragging the mouse
  var view = this; // in canvas callbacks, 'this' is the canvas, not the view

  // register canvas callbacks to mouse events
  canvas.onmousedown = function(e) {
    // TODO: what about right clicks? http://stackoverflow.com/a/322827/856897
    view.isMouseDown = true;
    var screenPos = getScreenPos(e);
    var pos = view.toBoardPos(screenPos); // screen to model coords
    model.selectPieceAt(pos.x, pos.y);
    // store dragging start position
    view.dragStart = {
      x : pos.x,
      y : pos.y
    };
  };

  canvas.onmouseup = function(e) {
    view.isMouseDown = false;
    if (model.draggedPiece) {
      var sPos = getScreenPos(e);
      var bPos = view.toBoardPos(sPos);
      model.dropPieceLocal(bPos.x, bPos.y); // drop the piece
    }
    view.dragStart = null; // stop dragging board or piece
  };

  // Don't redraw the canvas if the mouse moved but was not down.
  // The modes "drag a piece" or "slide the board" are in the model logic;
  // For the view, it's only about mouse movement.
  canvas.onmousemove = function(e) {
    if (view.isMouseDown) {
      var screenPos = getScreenPos(e);
      var pos = view.toBoardPos(screenPos); // screen to model coords
      var dx = pos.x - view.dragStart.x;
      var dy = pos.y - view.dragStart.y;
      if (model.draggedPiece) // a piece is being dragged
        model.movePieceRelative(dx, dy);
      else
        model.moveBoardRelative(dx, dy); // shift the board
      // in both cases: the mouse moved => recompute the dragging origin
      pos = view.toBoardPos(screenPos);
      view.dragStart = {
        x : pos.x,
        y : pos.y
      };
    }
  };

  canvas.onmouseout = function(e) {
    view.isMouseDown = false;
    if (model.draggedPiece) {
      var sPos = getScreenPos(e);
      var bPos = view.toBoardPos(sPos);
      model.dropPieceLocal(bPos.x, bPos.y); // drop the piece
    }
    view.dragStart = null; // stop dragging board or piece
  };

  this.scaleStep = 1.5; // how smooth is the zooming-in and out

  function onmousewheel(e) {
    e.preventDefault(); // dont scroll the window
    // detail for FF, wheelDelta for Chrome and IE
    var scroll = -e.wheelDelta || e.detail; // < 0 means forward/up, > 0 is down
    var isZoomingOut = scroll > 0;
    var screenPos = getScreenPos(e);
    model.zoomOnScreenPoint(isZoomingOut, view.scaleStep, screenPos);
  }
  canvas.addEventListener('DOMMouseScroll', onmousewheel, false); // FF
  canvas.addEventListener('mousewheel', onmousewheel, false); // Chrome, IE

  // get click position relative to the canvas's top left corner
  // adapted from http://www.quirksmode.org/js/events_properties.html
  // TODO: this does not take into account the canvas' border thickness
  function getScreenPos(e) {
    var posx;
    var posy;
    if (!e)
      var e = window.event;
    if (e.pageX || e.pageY) {
      posx = e.pageX - canvas.offsetLeft;
      posy = e.pageY - canvas.offsetTop;
    } else if (e.clientX || e.clientY) {
      posx = e.clientX + document.body.scrollLeft
          + document.documentElement.scrollLeft - canvas.offsetLeft;
      posy = e.clientY + document.body.scrollTop
          + document.documentElement.scrollTop - canvas.offsetTop;
    } else {
      console.log('Error: event did not contain mouse position.')
    }
    var res = {
      x : posx,
      y : posy
    };
    return res;
  }

  // ---------------------- VIEW ------------------------------

  var ctx = canvas.getContext('2d');

  // background image
  var BGIMG = new Image();
  BGIMG.src = "img/wood004.jpg";
  // "http://static1.grsites.com/archive/textures/wood/wood004.jpg";
  // wooden background from http://www.grsites.com/terms/
  // TODO: img.onload

  // draw the background
  function drawBoard() {
    ctx.save();
    var pattern = ctx.createPattern(BGIMG, 'repeat');
    ctx.fillStyle = pattern;
    // ctx.fillStyle = '#def'; // light blue
    var pos = view.toScreenPos(0, 0);
    var dims = view.toScreenDims(model.BOARD.w, model.BOARD.h);
    ctx.fillRect(pos.x, pos.y, dims.w, dims.h);
    ctx.restore();
  }

  // draw a gray grid showing where pieces can be dropped
  function drawGrid() {
    var g = model.GRID;
    ctx.save();
    // draw background image
    var pos = view.toScreenPos(g.x, g.y);
    var dims = view.toScreenDims(g.cellw * g.ncols, g.cellh * g.nrows);
    var w = dims.w, h = dims.h;
    ctx.fillStyle = '#fff';
    ctx.fillRect(pos.x, pos.y, dims.w, dims.h);
    ctx.globalAlpha = 0.2; // transparency
    ctx.drawImage(IMG, 0, 0, IMG.width, IMG.height, pos.x, pos.y, w, h);
    ctx.globalAlpha = 1;
    // draw grid lines
    ctx.strokeStyle = "#222"; // gray
    ctx.lineWidth = 1;
    ctx.beginPath();
    var screenPos;
    // draw vertical grid lines
    var grid_bottom = g.y + g.nrows * g.cellh;
    for ( var c = 0; c <= g.ncols; c++) {
      var x = g.x + c * g.cellw;
      screenPos = view.toScreenPos(x, g.y);
      ctx.moveTo(screenPos.x, screenPos.y);
      screenPos = view.toScreenPos(x, grid_bottom);
      ctx.lineTo(screenPos.x, screenPos.y);
    }
    // draw horizontal grid lines
    var grid_right = g.x + g.ncols * g.cellw;
    for ( var r = 0; r <= g.nrows; r++) {
      var y = g.y + r * g.cellh;
      screenPos = view.toScreenPos(g.x, y);
      ctx.moveTo(screenPos.x, screenPos.y);
      screenPos = view.toScreenPos(grid_right, y);
      ctx.lineTo(screenPos.x, screenPos.y);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }

  // draw pieces that are correctly placed in the grid (bound pieces)
  // and draw pieces that are movable (loose pieces)
  function drawPieces() {
    var p;
    for ( var pnum in model.boundPieces) {
      p = model.boundPieces[pnum];
      drawPiece(p);
    }
    for ( var pnum in model.loosePieces) {
      p = model.loosePieces[pnum];
      drawPiece(p);
    }
  }

  // Draw a piece, whether loose or bound
  function drawPiece(p) {
    var grid = model.GRID;
    var pos = view.toScreenPos(p.x, p.y);
    var dims = view.toScreenDims(grid.cellw, grid.cellh);
    var dw = dims.w, dh = dims.h;
    ctx.save();
    ctx.drawImage(IMG, p.sx, p.sy, p.sw, p.sh, pos.x, pos.y, dw, dh);
    // draw borders on top of pieces currently being dragged
    if (p.owner) { // piece is owned by another player
      ctx.strokeStyle = "#f0f"; // magenta
      ctx.globalAlpha = 0.5; // transparency
      var br = 1 / 15; // border ratio
      // screen thickness
      var t = view.toScreenDims(grid.cellw * br, grid.cellh * br).w;
      ctx.lineWidth = t;
      ctx.strokeRect(pos.x + t / 2, pos.y + t / 2, dw - t, dh - t);
    } else if (p == model.draggedPiece) { // piece I'm currently dragging
      ctx.strokeStyle = "#0ff"; // cyan
      ctx.globalAlpha = 0.5; // transparency
      var br = 1 / 15; // border ratio, in terms of cell dimensions
      // screen thickness
      var t = view.toScreenDims(grid.cellw * br, grid.cellh * br).w;
      ctx.lineWidth = t;
      ctx.strokeRect(pos.x + t / 2, pos.y + t / 2, dw - t, dh - t);
    }
    ctx.restore();
  }

  // first clean the whole canvas,
  // then draw in this order: grid, bound pieces, and loose pieces
  // public method of view so that model can call it
  this.drawAll = function() {
    var w = ctx.canvas.width;
    var h = ctx.canvas.height;
    ctx.fillStyle = '#000'; // black
    ctx.fillRect(0, 0, w, h);
    drawBoard();
    drawGrid();
    drawPieces();
  };

}