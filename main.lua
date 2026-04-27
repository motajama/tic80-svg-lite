local lovevec = require("runtime.lovevec")

local house_palette = {
  roof = {0.78, 0.29, 0.22, 1},
  wall = {0.88, 0.84, 0.72, 1},
  door = {0.36, 0.22, 0.12, 1},
  window = {0.78, 0.92, 1.0, 1},
  [12] = {0.95, 0.95, 0.95, 1},
}

local icon_house

function love.load()
  love.window.setTitle("SVG Lite Love2D Demo")
  love.graphics.setBackgroundColor(0.08, 0.09, 0.12, 1)
  icon_house = lovevec.loadvec("examples/house.lua", "icon_house")
end

function love.draw()
  if icon_house then
    lovevec.drawvec(icon_house, 80, 70, 8, house_palette)
  end

  love.graphics.setColor(0.95, 0.95, 0.95, 1)
  love.graphics.print("Love2D SVG Lite demo", 40, 24)
  love.graphics.print("Loaded from examples/house.lua via love.filesystem", 40, 220)
end
