-- TIC-80 demo
-- Paste runtime/ticvec.lua first, then generated icon tables, then this demo.

local house_pal={
 roof=6,
 wall=12,
 door=4,
 window=15,
}

local line_pal={
 spark=14,
 curve_a=11,
 curve_b=6,
}

function TIC()
 cls(0)

 -- assumes you generated:
 -- python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house
 -- python3 svg2ticvec.py examples/polyline.svg -o examples/polyline.lua -n icon_polyline
 -- python3 svg2ticvec.py examples/curve.svg -o examples/curve.lua -n icon_curve

 drawvec(icon_house,20,20,2,house_pal)
 drawvec(icon_polyline,90,20,2,line_pal)
 drawvec(icon_curve,20,85,3,line_pal)

 print("TIC-80 SVG Lite", 10, 118, 12)
 print("Label-driven palette roles", 10, 126, 13)
end
