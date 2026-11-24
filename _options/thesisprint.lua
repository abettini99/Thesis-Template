-- Reads an ICC colour profile's header and description, for the PDF/X output intent
-- (_options/documentmetadata.tex). Sets \thesisprofileclass (prtr for a printer profile),
-- \thesisprofilespace (CMYK, RGB, GRAY) and \thesisprofiledesc; all empty if the file is not a profile.
thesis = thesis or {}
function thesis.iccinfo(name)
  local class, space, desc = "", "", ""
  local path = kpse.find_file(name) or name
  local f = io.open(path, "rb")
  local d = f and f:read("*a") or ""
  if f then f:close() end
  if #d >= 132 and d:sub(37, 40) == "acsp" then
    local function u32(p) local a, b, c, e = d:byte(p, p + 3); return ((a * 256 + b) * 256 + c) * 256 + e end
    class, space = d:sub(13, 16), d:sub(17, 20):gsub(" ", "")
    for i = 0, u32(129) - 1 do
      local t = 133 + 12 * i
      if d:sub(t, t + 3) == "desc" then
        local o = u32(t + 4) + 1
        local kind = d:sub(o, o + 3)
        if kind == "desc" then                      -- ICC version 2: ASCII
          desc = d:sub(o + 12, o + 12 + u32(o + 8) - 2)
        elseif kind == "mluc" then                  -- ICC version 4: UTF-16BE, the first record
          local len, off = u32(o + 20), u32(o + 24)
          local s, out = d:sub(o + off, o + off + len - 1), {}
          for k = 1, #s - 1, 2 do out[#out + 1] = utf8.char(s:byte(k) * 256 + s:byte(k + 1)) end
          desc = table.concat(out)
        end
      end
    end
  end
  -- keep it plain text: no characters TeX would read as commands
  local clean = {}
  for _, c in utf8.codes(desc) do
    if c >= 32 and c ~= 92 and c ~= 123 and c ~= 125 and c ~= 35 and c ~= 37 and c ~= 36 and c ~= 38
       and c ~= 94 and c ~= 95 and c ~= 126 then clean[#clean + 1] = utf8.char(c) end
  end
  desc = table.concat(clean)
  tex.sprint("\\gdef\\thesisprofileclass{" .. class .. "}\\gdef\\thesisprofilespace{" .. space
    .. "}\\gdef\\thesisprofiledesc{" .. desc .. "}")
end

-- For an RGB photo (PNG or JPEG), the keywords that place it in the sRGB colour space (object `obj`):
-- LuaTeX writes images as device RGB and ignores a profile in the file. Grey, palette and CMYK images
-- are left as they are (tools/check_print.py names any that matter).
function thesis.imagecs(name, obj)
  local path = kpse.find_file(name) or name
  local f = io.open(path, "rb")
  if not f or not obj or obj == "" then if f then f:close() end return end
  local head = f:read(65536) or ""
  f:close()
  local rgb = false
  if head:sub(1, 8) == "\137PNG\r\n\26\n" then
    local ctype = head:byte(26)
    rgb = (ctype == 2 or ctype == 6)                 -- truecolour, with or without alpha
  elseif head:sub(1, 2) == "\255\216" then          -- JPEG: the number of components in the frame header
    local i = 3
    while i < #head - 9 do
      local marker = head:byte(i + 1)
      if head:byte(i) ~= 255 then break end
      if marker >= 192 and marker <= 207 and marker ~= 196 and marker ~= 200 and marker ~= 204 then
        rgb = head:byte(i + 9) == 3
        break
      end
      i = i + 2 + head:byte(i + 2) * 256 + head:byte(i + 3)
    end
  end
  if rgb then tex.sprint("colorspace " .. obj .. " ") end
end

-- For the printer: every RGB colour that LaTeX, xcolor or TikZ writes onto a page ("r g b rg", "... RG")
-- rewritten in the sRGB colour space explicitly ("/thesisSRGB cs r g b sc"), and equal components as
-- grey ("v g"), as each page is shipped out. One place for all of them, whichever package set the colour.
do
  local num = "(%-?%d*%.?%d+)"
  local pat = num .. "%s+" .. num .. "%s+" .. num .. "%s+(r[gG])"
  local pat2 = num .. "%s+" .. num .. "%s+" .. num .. "%s+(RG)"
  local function conv(a, b, c, op)
    local stroke = op == "RG"
    if tonumber(a) == tonumber(b) and tonumber(b) == tonumber(c) then
      return a .. (stroke and " G" or " g")
    end
    return stroke and ("/thesisSRGB CS " .. a .. " " .. b .. " " .. c .. " SC")
                  or ("/thesisSRGB cs " .. a .. " " .. b .. " " .. c .. " sc")
  end
  local function fix(s)
    if not s or not s:find("[rR][gG]") then return s end
    s = s:gsub(num .. "(%s+)" .. num .. "(%s+)" .. num .. "%s+rg", function(a, _, b, _, c) return conv(a, b, c, "rg") end)
    s = s:gsub(num .. "(%s+)" .. num .. "(%s+)" .. num .. "%s+RG", function(a, _, b, _, c) return conv(a, b, c, "RG") end)
    return s
  end
  local whatsit = node.id("whatsit")
  local hlist, vlist = node.id("hlist"), node.id("vlist")
  local literal = node.subtype("pdf_literal")
  local colorstack = node.subtype("pdf_colorstack")
  local glue, disc = node.id("glue"), node.id("disc")
  local function walk(head)
    for n in node.traverse(head) do
      if n.id == hlist or n.id == vlist then
        walk(n.list)
      elseif n.id == glue and n.leader then
        walk(n.leader)
      elseif n.id == disc then
        walk(n.pre) walk(n.post) walk(n.replace)
      elseif n.id == whatsit and (n.subtype == literal or n.subtype == colorstack) then
        local d = n.data
        if type(d) == "string" then
          local f = fix(d)
          if f ~= d then n.data = f end
        end
      end
    end
  end
  thesis.srgbfix = fix
  function thesis.srgbpages()
    luatexbase.add_to_callback("pre_shipout_filter", function(head) walk(head) return true end, "thesis.srgb")
    -- (code run at shipout, such as LaTeX's own late Lua, writes through pdf.print: the same there)
    local print = pdf.print
    pdf.print = function(a, b)
      if b ~= nil then return print(a, type(b) == "string" and fix(b) or b) end
      return print(type(a) == "string" and fix(a) or a)
    end
  end
end
