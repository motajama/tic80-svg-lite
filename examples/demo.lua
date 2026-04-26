-- TIC-80 demo
-- Paste runtime/ticvec.lua first, then generated icon tables, then this demo.

function TIC()
 cls(0)

 -- assumes you generated:
 -- python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house
 -- python3 svg2ticvec.py examples/polyline.svg -o examples/polyline.lua -n icon_polyline
 -- python3 svg2ticvec.py examples/curve.svg -o examples/curve.lua -n icon_curve

 drawvec(icon_house,20,20,2)
 drawvec(icon_polyline,90,20,2)
 drawvec(icon_curve,20,85,3)

 print("TIC-80 SVG Lite", 10, 126, 12)
end
