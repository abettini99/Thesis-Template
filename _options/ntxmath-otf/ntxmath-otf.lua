-- ntxmath-otf.lua: run-time helper for ntxmath-otf.sty (picks MTPro2 glyphs by name)
ntxmathotf = ntxmathotf or {}
ntxmathotf.litebm = ntxmathotf.litebm or {}
ntxmathotf.vfchars = {}                             -- virtual fonts: font id -> characters
ntxmathotf.vfbase = {}                              -- virtual fonts: font id -> OpenType font id
ntxmathotf.basedata = {}                            -- those OpenType fonts: font id -> font table
-- every file through TeX's own search paths (TEXINPUTS too, e.g. a Fonts/ folder added
-- by latexmkrc), never a fixed location
local function find(name, fmt)
  return kpse.find_file(name, fmt or "lua") or kpse.find_file(name, "tex")
end
ntxmathotf.find = find
local function load(name)
  local p = find(name .. ".lua")
  if not p then error("ntxmath-otf: cannot find " .. name .. ".lua") end
  return dofile(p)
end
function ntxmathotf.fontdir(name)                  -- folder of an OpenType font ("" if not found)
  local p = find(name, "opentype fonts")
  tex.sprint(-2, p and (p:match("^(.*/)") or "./") or "")
end
local V = load("ntxmath-otf-variants")
-- TeX's exact glyph boxes (luaotfload measures outlines: rounded, and with overshoots)
local D = load("ntxmath-otf-dims")
ntxmathotf.italic = {}                               -- font id -> {char -> subscript kern}
ntxmathotf.accxh = {}                                -- font id -> {glyph index -> accent x-height}
-- newtx's design for a size, as its .fd files choose it: 1 text (8.6 pt up), 2 script
-- (6.3 to 8.6 pt), 3 scriptscript (below 6.3 pt); sizes before the package's scale option
function ntxmathotf.design(sp)
  local pt = sp / 65536 / (ntxmathotf.scale or 1)
  return pt < 6.2999 and 3 or pt < 8.5999 and 2 or 1
end
luatexbase.add_to_callback("luaotfload.patch_font", function(tfm, spec, id)
  local d = D[tfm.psname or (tfm.properties or {}).psname or ""]
  if not d or not tfm.characters then return end
  -- the design of this size: every character with optical sizes takes that size's glyph (with
  -- its kerns and variants, as luaotfload's 'ssty' gives them; unicode-math's 'ssty' is off)
  local oinfo = D.info and D.info[tfm.psname]
  local lvl = ntxmathotf.design(tfm.parameters.size)
  if oinfo and oinfo.optical and lvl > 1 then
    local byidx = {}
    for u, c in pairs(tfm.characters) do
      if c.index and (not byidx[c.index] or u >= 0xF0000) then byidx[c.index] = u end
    end
    local o, swap = oinfo.optical, {}
    for i = 1, #o, 3 do swap[o[i]] = o[i + lvl - 1] end
    local novar = {}
    for _, g in ipairs(oinfo.novar or {}) do novar[g] = true end
    local new = {}
    for u, c in pairs(tfm.characters) do
      local t = c.index and swap[c.index]
      local src = t and t ~= c.index and byidx[t] and tfm.characters[byidx[t]]
      if src then                                    -- (also glyphs set by name: private codes)
        local cc = {}
        for k, v in pairs(src) do cc[k] = v end
        cc.unicode, cc.tounicode = c.unicode, c.tounicode
        if not novar[t] then
          for _, k in ipairs({ "next", "vert_variants", "horiz_variants", "extensible" }) do
            if cc[k] == nil then cc[k] = c[k] end         -- (sizes hang on the text glyph)
          end
        end
        new[u] = cc
      end
    end
    for u, cc in pairs(new) do tfm.characters[u] = cc end
  end
  -- a glyph with several code points (A and Alpha, \\partial's U+2202 and U+1D715, | and
  -- \\mid): luaotfload gives its kerns and math kerns to one code point only; TeX looks
  -- characters up by the code it was given, so every code point needs them
  local codes = {}
  for u, c in pairs(tfm.characters) do
    if c.index then codes[c.index] = codes[c.index] or {}; table.insert(codes[c.index], u) end
  end
  for _, us in pairs(codes) do
    if #us > 1 then
      local kerns, mk
      for _, u in ipairs(us) do
        local c = tfm.characters[u]
        if c.kerns then kerns = kerns or {}; for v, k in pairs(c.kerns) do kerns[v] = kerns[v] or k end end
        mk = mk or c.mathkern
      end
      for _, u in ipairs(us) do
        local c = tfm.characters[u]
        if kerns then c.kerns = c.kerns or {}; for v, k in pairs(kerns) do c.kerns[v] = c.kerns[v] or k end end
        c.mathkern = c.mathkern or mk
      end
    end
  end
  for _, c in pairs(tfm.characters) do            -- ... and as the second of a pair too
    if c.kerns then
      local add = {}
      for v, k in pairs(c.kerns) do
        local cv = tfm.characters[v]
        for _, w in ipairs(cv and cv.index and codes[cv.index] or {}) do
          if w ~= v and not c.kerns[w] then add[w] = k end
        end
      end
      for w, k in pairs(add) do c.kerns[w] = k end
    end
  end
  -- the subscript tuck (TeX's italic correction) is applied by the package, always: take the
  -- math kerns out of LuaTeX's hands (it applies them only to some subscripts)
  local ik = {}
  for u, c in pairs(tfm.characters) do
    local mk = c.mathkern and c.mathkern.bottom_right
    if mk and mk[1] and mk[1].kern then ik[u] = mk[1].kern; c.mathkern = nil end
  end
  if id then ntxmathotf.italic[id] = ik end
  local f = tfm.parameters.factor or (tfm.parameters.size / (tfm.units_per_em or 1000))
  local at = {}
  for i = 1, #d, 4 do at[d[i]] = i end
  for _, c in pairs(tfm.characters) do             -- c.index: the glyph actually used
    local i = c.index and at[c.index]               -- (after 'ssty' in script fonts)
    if i then
      c.width, c.height, c.depth = math.floor(d[i+1] * f + 0.5), math.floor(d[i+2] * f + 0.5),
        math.floor(d[i+3] * f + 0.5)
    end
  end
  -- boxes from TeX's fix_words where the glyph's box is the TFM's: the sp TeX gets
  if oinfo and oinfo.fix and ntxmathotf.scaler then
    local fx, scs = {}, {}
    local o = oinfo.fix
    for i = 1, #o, 5 do fx[o[i]] = i end
    local size = tfm.parameters.size
    for _, c in pairs(tfm.characters) do
      local i = c.index and fx[c.index]
      if i then
        local k = o[i + 1]
        local sc = scs[k] or ntxmathotf.scaler(size * k)
        scs[k] = sc
        if o[i + 2] then c.width = sc(o[i + 2]) end
        if o[i + 3] then c.height = sc(o[i + 3]) end
        if o[i + 4] then c.depth = sc(o[i + 4]) end
      end
    end
  end
  -- the subscript tucks to the sp: the italic corrections scaled as TeX scales them (the
  -- font's math kerns are whole units)
  if oinfo and oinfo.tuck and #oinfo.tuck > 0 and ntxmathotf.scaler and id and ntxmathotf.italic[id] then
    local tk, scs, ik = {}, {}, ntxmathotf.italic[id]
    local o = oinfo.tuck
    for i = 1, #o, 3 do tk[o[i]] = i end
    for u, c in pairs(tfm.characters) do
      local i = c.index and tk[c.index]
      if i and ik[u] then
        local k = o[i + 1]
        local sc = scs[k] or ntxmathotf.scaler(tfm.parameters.size * k)
        scs[k] = sc
        ik[u] = -sc(o[i + 2])
      end
    end
  end
  -- accent positions from the unrounded attachments (TeX places accents to the sp: the
  -- font's whole units are a unit off at sizes other than 10 pt)
  if oinfo and oinfo.accent then
    local ac = {}
    for i = 1, #oinfo.accent, 2 do ac[oinfo.accent[i]] = oinfo.accent[i + 1] end
    for _, c in pairs(tfm.characters) do
      local a = c.index and ac[c.index]
      if a and c.top_accent then c.top_accent = math.floor(a * f + 0.5) end
    end
  end
  -- (accents whose fonts' x-heights differ: by glyph index, for this font instance)
  if oinfo and oinfo.accxh and #oinfo.accxh > 0 then
    local ax = {}
    for i = 1, #oinfo.accxh, 2 do ax[oinfo.accxh[i]] = oinfo.accxh[i + 1] end
    ntxmathotf.accxh[id] = ax
  end
  -- TeX lowers an accent by at most the x-height of the accent's font, which is the script
  -- (scriptscript) size's own font in sub- and superscripts; OpenType has one value
  local info, mp = D.info and D.info[tfm.psname], tfm.mathparameters
  local x = tfm.characters[0x1D465]
  if info and mp and x and mp.AccentBaseHeight then
    local level = 1
    for k, g in ipairs(info.probe) do if x.index == g then level = k end end
    local abh = math.floor(info.xheight[level] * tfm.parameters.size + 0.5)
    if mp.FlattenedAccentBaseHeight then
      mp.FlattenedAccentBaseHeight = math.floor(mp.FlattenedAccentBaseHeight * abh / mp.AccentBaseHeight + 0.5)
    end
    mp.AccentBaseHeight = abh
  end
  -- (an instance with another design's glyphs under the same codes is a PDF font of its
  -- own: instances of one font file share one embedded subset, chosen by character code)
  if oinfo and oinfo.optical and lvl > 1 then
    tfm.psname = (tfm.psname or "NewTXMath") .. "-D" .. lvl
    if tfm.fullname then tfm.fullname = tfm.fullname .. "-D" .. lvl end
  end
end, "ntxmath-otf.dims")
local function fam() return tex.getmathcode(0x2211)[2] end
local function slot(name)
  local f = fam()
  return luaotfload.aux.slot_of_name(node.family_font(f, 0), name), f
end
-- Legacy layer: MTPro2's TFM fonts rebuilt as virtual fonts on the OpenType glyphs, so that
-- LaTeX's own symbol families and mtpro2.sty's macros (which load mt2exe etc. directly)
-- behave exactly as with the Type 1 fonts. A font named "ntxvf:<tfm name>" is built here.
local TF
local function scaler(z)                           -- TeX's store_scaled (tex.web 571-572)
  local alpha = 16
  while z >= 0x800000 do z = z // 2; alpha = alpha + alpha end
  local beta = 256 // alpha
  alpha = alpha * z
  return function(v)
    if v < 0 then v = v + 0x100000000 end
    local a, b, c, d = v >> 24, (v >> 16) & 255, (v >> 8) & 255, v & 255
    local sw = (((((d * z) // 256) + (c * z)) // 256) + (b * z)) // beta
    return a == 255 and sw - alpha or sw
  end
end
ntxmathotf.scaler = scaler
local basefonts = {}
local function basefont(otf, size)
  local key = otf .. "@" .. size
  if not basefonts[key] then
    local data = fonts.definers.read("[" .. (find(otf, "opentype fonts") or otf) .. "]:mode=base;", size)
    local codes = {}                                -- glyph index -> character code
    for u, c in pairs(data.characters) do
      if c.index and not codes[c.index] then codes[c.index] = u end
    end
    basefonts[key] = { font.define(data), codes }
    ntxmathotf.basedata[basefonts[key][1]] = data
  end
  return basefonts[key][1], basefonts[key][2]
end
function ntxmathotf.virtual(name, size)
  TF = TF or load("ntxmath-otf-tfm")
  local T = TF[name]
  if not T then return nil end
  if size < 0 then size = (-size * T.ds) // 1000 end
  local sc = scaler(size)
  local bid, codes = basefont(T.otf, (size + T.scale // 2) // T.scale)
  local K = {}
  for i, k in ipairs(T.K) do K[i] = sc(k) end
  local chars = {}
  for slot, c in pairs(T.c) do
    local u = codes[c[5]]
    if u then
      local ch = { width = sc(c[1]), height = sc(c[2]), depth = sc(c[3]), italic = sc(c[4]),
        commands = c[6] ~= 0 and { { "down", sc(c[6]) }, { "slot", 1, u } } or { { "slot", 1, u } } }
      if c[7] then ch.next = c[7] end
      local e = c[8]
      if e then
        ch.extensible = { top = e[1] ~= 0 and e[1] or nil, mid = e[2] ~= 0 and e[2] or nil,
          bot = e[3] ~= 0 and e[3] or nil, rep = e[4] }
      end
      if c[9] then
        ch.kerns = {}
        for i = 1, #c[9], 2 do ch.kerns[c[9][i]] = K[c[9][i + 1]] end
      end
      chars[slot] = ch
    end
  end
  local p, params = T.p, {}
  local names = { "slant", "space", "space_stretch", "space_shrink", "x_height", "quad", "extra_space" }
  for i, v in ipairs(p) do
    local val = i == 1 and v // 16 or sc(v)
    params[names[i] or i] = val
  end
  return { name = "ntxvf:" .. name, type = "virtual", size = size, designsize = T.ds,
    characters = chars, fonts = { { id = bid } }, parameters = params }
end
-- Font loading: build the virtual fonts, and apply the package's scale option to every
-- MTPro2 font (the OpenType ones and the virtual ones), as a size factor at load time.
-- Wraps whatever font loader is installed (luaotfload's, or another package's wrapper).
ntxmathotf.scale = ntxmathotf.scale or 1
do
  local desc = luatexbase.callback_descriptions("define_font")[1]
  local define = desc and luatexbase.remove_from_callback("define_font", desc) or font.read_tfm
  luatexbase.add_to_callback("define_font", function(name, size, id)
    local s = ntxmathotf.scale
    local n = name:match("^ntxvf:(.+)$")
    if s ~= 1 and size > 0 and (n or name:find("NewTXMath", 1, true)) then
      size = math.floor(size * s + 0.5)
    end
    if n then
      local f = ntxmathotf.virtual(n, size)
      if f then ntxmathotf.vfchars[id] = f.characters; ntxmathotf.vfbase[id] = f.fonts[1].id; return f end
    end
    return define(name, size, id)
  end, "ntxmath-otf.define_font")
end
-- Before LuaTeX converts a formula, adjust two things it does differently from TeX:
-- * a large operator without \\limits or \\nolimits is set like \\nolimits outside display
--   style (italic correction between operator and scripts); LuaTeX does that only for an
--   explicit \\nolimits;
-- * a subscript tucks under a character's italic correction whatever it contains: add the
--   kern at the start of the subscript (LuaTeX's math kerns would cover only some cases).
do
  local NOAD, STYLE, FRAC, CHOICE, RAD, ACC, SUBML, MCHAR = node.id("noad"), node.id("style"),
    node.id("fraction"), node.id("choice"), node.id("radical"), node.id("accent"),
    node.id("sub_mlist"), node.id("math_char")
  local names = { display = 0, crampeddisplay = 1, text = 2, crampedtext = 3, script = 4,
    crampedscript = 5, scriptscript = 6, crampedscriptscript = 7 }
  local function num(s) return type(s) == "number" and s or names[s] or 2 end
  local function sup(s) return (s < 4 and 4 or 6) + s % 2 end
  local function sub(s) return sup(s) | 1 end
  local function numer(s) return s < 2 and 2 + s % 2 or (s < 6 and s + 2 or s) end
  local function size(s) return s < 4 and 0 or (s < 6 and 1 or 2) end
  -- (LuaTeX versions differ here: newer ones box an operator with limits including its
  -- italic correction, older ones do not; try one operator to see which twin matches TeX)
  local limits_map = {}
  local twins_ok
  local function limits_char(nu, s)
    local id = node.family_font(nu.fam, size(s))
    local m = limits_map[id]
    if not m then
      m = {}
      local f, probe = font.getfont(id), nil
      for a, b in pairs(V.limits or {}) do
        local ca, cb = luaotfload.aux.slot_of_name(id, a), luaotfload.aux.slot_of_name(id, b)
        if ca and cb then
          m[ca] = cb
          local c = f and f.characters[cb]
          if c and (c.italic or 0) > 0 and (not probe or cb < probe) then probe = cb end
        end
      end
      -- the twins are for engines that add the italic correction to the box (an engine
      -- property: tested once, on an operator with an italic correction)
      if twins_ok == nil and probe then
        local cw, ci = f.characters[probe].width, f.characters[probe].italic
        local op = node.new("noad", 2)
        op.nucleus = node.new("math_char"); op.nucleus.fam, op.nucleus.char = nu.fam, probe
        local box = node.hpack(node.mlist_to_hlist(op, "text", false))
        twins_ok = math.abs(box.width - (cw + ci)) <= math.abs(box.width - cw)
        node.flush_list(box)
      end
      if twins_ok == false then m = {} end
      limits_map[id] = m
    end
    return m[nu.char]
  end
  local function italic_kern(nu, s)
    local t = ntxmathotf.italic[node.family_font(nu.fam, size(s))]
    return t and t[nu.char]
  end
  local walk
  -- nodes built here have no attributes: give them those of the formula part they replace
  -- (tagged PDF marks the content with attributes; without them it falls out of the structure)
  local function adopt(x, src)
    local a = src and src.attr
    if not a then return end
    while x do
      if not x.attr then x.attr = a end
      if (x.id == node.id("hlist") or x.id == node.id("vlist")) and x.head then adopt(x.head, src) end
      x = x.next
    end
  end
  local function list(f, s) if f and f.id == SUBML then f.head = walk(f.head, s) end end
  local snames = { [0] = "display", "crampeddisplay", "text", "crampedtext", "script",
    "crampedscript", "scriptscript", "crampedscriptscript" }
  -- TeX's radical rule is as thick as the sign it uses; in script sizes the small sign is
  -- thicker than the default rule: set such a radical here, with the right thickness
  local function radical(n, s)
    local p = V.texparams
    if not (p and p.radsign) or not n.nucleus then return n end
    local u = ntxmathotf.fontsize[node.family_font(fam(), size(s))]
    local z = ntxmathotf.design(u)                     -- (the design of that size, as the .fd files)
    if z == 1 then return n end                       -- (the text design: the default rule)
    local tmp
    if n.nucleus.id == SUBML then tmp = node.copy_list(n.nucleus.head)
    else tmp = node.new("noad", 0); tmp.nucleus = node.copy(n.nucleus) end
    local x = node.hpack(node.mlist_to_hlist(tmp, snames[s | 1], false))
    local theta = ntxmathotf.S(p.rule, u)
    local need = x.height + x.depth + theta + theta // 4 + theta
    node.flush_list(x)
    if need > ntxmathotf.S(p.radsign[z], u) then return n end   -- a larger sign: the default rule
    list(n.nucleus, s | 1); list(n.degree, 6)
    local sub, sup = n.sub, n.sup
    n.sub, n.sup = nil, nil
    local old = tex.getmath("radicalrule", snames[s])
    tex.setmath("radicalrule", snames[s], ntxmathotf.S(p.radrule[z], u))
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local box = node.hpack(node.mlist_to_hlist(n, snames[s], false))
    tex.setmath("radicalrule", snames[s], old)
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    adopt(box, n); ord.attr, nu.attr = n.attr, n.attr
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  -- Lite \\bm / \\hm (no bold MTPro2 fonts): what has the \\bm attribute becomes newtx bold
  -- (letters, Greek, digits: real bold, like the Type 1 set-up), the bold font of an alphabet
  -- that has one, or else bm.sty's poor man's bold (three copies, .4mu apart, raised 1.5x)
  local LB = ntxmathotf.litebm
  local function pmb(nc, s, subtype)
    local tmp = node.new("noad", subtype or 0)
    tmp.nucleus = nc
    local b = node.hpack(node.mlist_to_hlist(tmp, snames[s], false))
    local r = s < 4 and 1 or tonumber(token.get_macro(s < 6 and "defaultscriptratio"
      or "defaultscriptscriptratio") or "") or (s < 6 and 0.7 or 0.5)
    local d = math.floor(0.4 / 18 * tex.getmath("quad", "text") * r + 0.5)
    local c1, c2 = node.copy(b), node.copy(b)
    c2.shift = -math.floor(1.5 * d + 0.5)
    local r1, r2 = node.hpack(c1, 0, "exactly"), node.hpack(c2, 0, "exactly")
    local k1, k2 = node.new("kern"), node.new("kern")
    k1.kern, k2.kern = d, d
    r1.next, k1.prev = k1, r1; k1.next, r2.prev = r2, k1; r2.next, k2.prev = k2, r2
    k2.next, b.prev = b, k2
    local sb = node.new("sub_box")
    sb.head = node.hpack(r1)
    adopt(sb.head, nc); sb.attr = nc.attr
    return sb
  end
  local BOLDCP = { { 0x1D400, 0x1D433 }, { 0x1D468, 0x1D49B }, { 0x1D4D0, 0x1D503 },
    { 0x1D56C, 0x1D59F }, { 0x1D5D4, 0x1D607 }, { 0x1D63C, 0x1D66F }, { 0x1D6A8, 0x1D6E1 },
    { 0x1D71C, 0x1D755 }, { 0x1D756, 0x1D7C9 }, { 0x1D7CA, 0x1D7CB }, { 0x1D7CE, 0x1D7D7 },
    { 0x1D7EC, 0x1D7F5 } }
  local function boldcp(c)
    for _, r in ipairs(BOLDCP) do if c >= r[1] and c <= r[2] then return true end end
  end
  local FENCE, FRAC2 = node.id("fence"), node.id("fraction")
  local function bold(nc, s, subtype)           -- a math_char under \\bm: the field's new value
    if not (nc and nc.id == MCHAR) then return nc end
    local a = node.has_attribute(nc, LB.attr)
    if not a then return nc end
    node.unset_attribute(nc, LB.attr)             -- (once: the walk can meet it again)
    local m = LB.map and nc.fam == fam() and LB.map[nc.char]
    if m and LB[m[1]] then nc.fam, nc.char = LB[m[1]], m[2]; return nc end
    local main = nc.fam == fam()
    if main and boldcp(nc.char) then return nc end  -- already a bold letter (\\mathbf, \\symbf)
    local nb = main and V[a == 1 and "nobold:bold" or "nobold:heavy"]
    if nb and nb[nc.char] and (nc.char >= 0x1D434 and nc.char <= 0x1D467 or nc.char == 0x210E) then
      return nc                 -- (bm.sty: a letter typed as such keeps its font when its family
    end                         -- has no such weight; a command like \\alpha gets poor man's bold)
    local f = not (nb and nb[nc.char]) and LB.fams[a] and LB.fams[a][nc.fam]
    if f and main and nc.char >= 0xF0000 then       -- a glyph set by name (private code):
      local z = size(s)                             -- the same name in the bold font
      local name = ntxmathotf.byslot[nc.char]
      local ok, slot = pcall(luaotfload.aux.slot_of_name, node.family_font(f, 0), name or "")
      if name and ok and slot then nc.fam, nc.char = f, slot; return nc end
      f = nil
    end
    if f then nc.fam = f; return nc end
    f = LB.fontmap and LB.fontmap[a][node.family_font(nc.fam, size(s))]
    if f then nc.fam = f; return nc end            -- (a math alphabet's bold)
    if not main and not LB.symfam[nc.fam] then return nc end  -- (an alphabet: no poor man's bold)
    return pmb(nc, s, subtype)
  end
  local boldrad, boldfrac, todirect = {}, {}, node.direct.todirect
  local function fams(n)                        -- the bold families for n's attribute, if any
    local a = node.has_attribute(n, LB.attr)
    return a and LB.fams[a]
  end
  local function lite(n, s)
    local id = n.id
    if id == NOAD then
      n.nucleus = bold(n.nucleus, s, (n.subtype >= 1 and n.subtype <= 3) and n.subtype or 0)
    elseif id == ACC or id == RAD then
      n.nucleus = bold(n.nucleus, s | 1)
      local t = fams(n)
      if t and id == ACC then                     -- the accent itself, if its font has a bold
        for _, k in ipairs({ "accent", "bot_accent" }) do
          local ok, c = pcall(function() return n[k] end)
          if ok and c and c.fam and t[c.fam] then
            if c.fam == fam() and c.char and c.char >= 0xF0000 then   -- (set by name: the same
              local name = ntxmathotf.byslot[c.char]                    -- name in the bold font)
              local ok2, sl = pcall(luaotfload.aux.slot_of_name, node.family_font(t[c.fam], 0), name or "")
              if name and ok2 and sl then c.char = sl end
            end
            c.fam = t[c.fam]
          end
        end
      elseif t and n.left then                    -- the radical sign
        local d = n.left
        if t[d.small_fam] or t[d.large_fam] then boldrad[todirect(n)] = node.has_attribute(n, LB.attr) end
        if t[d.small_fam] then d.small_fam = t[d.small_fam] end
        if t[d.large_fam] then d.large_fam = t[d.large_fam] end
      end
      if id == RAD then n.degree = bold(n.degree, 6) end
    elseif id == FENCE then                       -- \\left( .. \\right): bold delimiters
      local t, d = fams(n), n.delim
      if t and d then
        if t[d.small_fam] then d.small_fam = t[d.small_fam] end
        if t[d.large_fam] then d.large_fam = t[d.large_fam] end
      end
      return
    elseif id == FRAC2 then                       -- the bold version's rule (bm.sty sets
      local t = fams(n)                           -- such a group in the bold version)
      local bf = t and t[fam()]
      local id2 = bf and node.family_font(bf, size(s))
      local mc = id2 and id2 > 0 and font.getfont(id2) and font.getfont(id2).MathConstants
      local w = n.width or 0
      if mc and mc.FractionRuleThickness and (w < 0 or w >= 0x40000000) then
        boldfrac[todirect(n)] = { mc.FractionRuleThickness, node.has_attribute(n, LB.attr) }
      end
      return
    else return end
    n.sup, n.sub = bold(n.sup, sup(s)), bold(n.sub, sub(s))
  end
  -- TeX's radical rule is as thick as the sign it chose is high (a large sign, a bold one
  -- under \\bm), OpenType has one value: where they differ, set the radical here
  local GLYPH, HLIST, VLIST = node.id("glyph"), node.id("hlist"), node.id("vlist")
  local function firstglyph(h)
    for x in node.traverse(h) do
      if x.id == GLYPH then return x end
      if (x.id == HLIST or x.id == VLIST) and x.head then
        local g = firstglyph(x.head)
        if g then return g end
      end
    end
  end
  local function exactradical(n, s, force)
    list(n.nucleus, s | 1); list(n.degree, 6)
    local trial = node.hpack(node.mlist_to_hlist(node.copy(n), snames[s], false))
    local g = firstglyph(trial.head)
    local f = g and font.getfont(g.font)
    local chars = f and f.characters or (g and ntxmathotf.vfchars[g.font])
    local c = chars and chars[g.char]
    node.flush_list(trial)
    local old = tex.getmath("radicalrule", snames[s])
    local h = c and c.height
    if not h or h <= 0 or (h == old and not force) then return n end
    local sub, sup = n.sub, n.sup
    n.sub, n.sup = nil, nil
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local st, saved = snames[s], {}
    local set = { radicalrule = h }
    -- (LaTeX's \\sqrt[n] is \\root, set in a box: under bm.sty that box is in the bold
    -- version, with the bold fonts' clearance; a plain \\sqrt keeps the formula's)
    local isroot = node.has_attribute(n, luatexbase.attributes["MTP@rootattr"] or -1)
    local bp = force and isroot and V[force == 2 and "texparams:heavy" or "texparams:bold"]
    if bp then
      local u = ntxmathotf.fontsize[node.family_font(fam(), size(s))]
    local z = ntxmathotf.design(u)                     -- (the design of that size, as the .fd files)
      local th = math.floor(bp.rule * u + 0.5)
      local phi = s < 2 and math.floor(bp.xheight[z] * u + 0.5) or th
      set.radicalvgap, set.radicalkern = th + math.abs(phi) // 4, th
    end
    for k, v in pairs(set) do saved[k] = tex.getmath(k, st); tex.setmath(k, st, v) end
    local box = node.hpack(node.mlist_to_hlist(n, st, false))
    for k, v in pairs(saved) do tex.setmath(k, st, v) end
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    adopt(box, n); ord.attr, nu.attr = n.attr, n.attr
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  -- an accent from the extension font (\\wwhat, \\wwtilde, \\wwcheck): TeX lowers it by at
  -- most that font's x-height (in a script: the extension font scaled), OpenType by the
  -- symbol fonts' (AccentBaseHeight): set the accent's kern as TeX does
  local KERN = node.id("kern")
  local extacc
  local function isext(n)
    if not extacc then
      extacc = {}
      for name, f in pairs(V.accentfam or {}) do
        if f == "largesymbols" and V.accent[name] then
          local sl = slot(V.accent[name])
          if sl then extacc[sl] = true end
        end
      end
    end
    local ok, a = pcall(function() return n.accent end)
    return ok and a and a.char and extacc[a.char] and a.fam == fam()
  end
  local function accglyph(h)                  -- the accent glyph of an accent's vbox
    for x in node.traverse(h) do
      if x.id == VLIST and x.head then
        local a = x.head
        if a.id == KERN then a = a.next end
        if a and a.id == HLIST and a.head then
          for y in node.traverse(a.head) do if y.id == node.id("glyph") then return y end end
        end
      elseif x.id == HLIST and x.head then
        local y = accglyph(x.head)
        if y then return y end
      end
    end
  end
  local function accentfix(h, A, hc)
    local changed = false
    for x in node.traverse(h) do
      if x.id == VLIST and x.head then
        local a = x.head
        if hc and a.id == KERN and a.next then          -- (the engine's top kern: again below)
          x.head = node.remove(x.head, a); node.free(a); a = x.head
        end
        local k = a.next
        local b = k and k.next
        -- (an accent's box has width 0; a scripts' vbox is not one)
        if k and k.id == KERN and b and not b.next and (b.id == HLIST or b.id == VLIST)
            and a.id == HLIST and a.width == 0 then
          if b.id == VLIST then accentfix(b, A) end  -- (a nested accent: b and no further)
          -- delta = min(h, x-height), plus (with scripts) the box's height above the character's
          k.kern = hc and -(math.min(hc, A) + b.height - hc) or -math.min(b.height, A)
          x.height = a.height + a.depth + k.kern + b.height
          if hc and x.height < b.height then
            local t = node.new("kern"); t.kern = b.height - x.height
            x.head = node.insert_before(x.head, a, t); x.height = b.height
          end
          changed = true
        end
      elseif x.id == HLIST and x.head and accentfix(x.head, A, hc) then
        local w, hh, d = node.dimensions(x.head)
        x.height, x.depth = math.max(hh - (0), 0), d
        changed = true
      end
    end
    return changed
  end
  -- a subscript tucks under the character's italic correction (TeX moves the scripts of
  -- an accented character onto the character; \\overline, \\underline box their nucleus)
  local function tuck(n, s)
    local nu, sb = n.nucleus, n.sub
    local k = (n.id == NOAD and n.subtype < 10 or n.id == ACC) and nu and nu.id == MCHAR and sb
      and italic_kern(nu, s)
    if k and k ~= 0 then
      if sb.id ~= SUBML then                    -- x_i: make the subscript a list
        local ml, ord = node.new("sub_mlist"), node.new("noad", 0)
        ord.nucleus, ml.head, n.sub = sb, ord, nil
        n.sub, sb = ml, ml
      end
      local kn = node.new("kern")
      kn.kern = k
      sb.head = node.insert_before(sb.head, sb.head, kn)
    end
    return sb
  end
  local function extaccent(n, s)
    local p = V.texparams
    local nu = n.nucleus
    local hc                                  -- scripts on a character: TeX's own case, the
    if nu and nu.id == MCHAR and (n.sub or n.sup) then   -- accent placed as on the bare one
      local f = font.getfont(node.family_font(nu.fam, size(s)))
      local c = f and f.characters[nu.char]
      hc = c and (c.height or 0) or nil
    end
    if hc then
      local sb = tuck(n, s)
      list(n.sup, sup(s)); list(sb, sub(s))
    end
    -- nested accents (\\wwhat{\\wwhat{x}}): the engine places them as amsmath does; only
    -- their kerns are fixed below
    local inner = n
    while inner.nucleus and inner.nucleus.id == SUBML and inner.nucleus.head
        and inner.nucleus.head.id == ACC and not inner.nucleus.head.next
        and not inner.nucleus.head.sub and not inner.nucleus.head.sup
        and (V.accentxh or isext(inner.nucleus.head)) do
      inner = inner.nucleus.head
    end
    list(inner.nucleus, s | 1)
    local sub, sup = n.sub, n.sup
    if hc then sub, sup = nil, nil else n.sub, n.sup = nil, nil end
    local prev, nxt = n.prev, n.next
    n.prev, n.next = nil, nil
    local u = ntxmathotf.fontsize[node.family_font(fam(), size(s))]
    local box = node.hpack(node.mlist_to_hlist(n, snames[s], false))
    local A = p.xheight3 and math.floor(p.xheight3 * u + 0.5)
    local g = accglyph(box.head)                  -- (the accent's own font's x-height)
    local ax = g and ntxmathotf.accxh[g.font]
    if ax then
      local c = font.getfont(g.font).characters[g.char]
      local xh = c and c.index and ax[c.index]
      if xh then A = math.floor(xh * ntxmathotf.fontsize[g.font] + 0.5) end
    end
    if A and accentfix(box.head, A, hc) then
      local inner = box.head
      box.head = nil
      node.free(box)
      box = node.hpack(inner)
    end
    local ord, nu = node.new("noad", 0), node.new("sub_box")
    adopt(box, n); ord.attr, nu.attr = n.attr, n.attr
    nu.head, ord.nucleus, ord.sub, ord.sup = box, nu, sub, sup
    if prev then prev.next = ord; ord.prev = prev end
    if nxt then nxt.prev = ord; ord.next = nxt end
    return ord
  end
  walk = function(head, s)
    local n = head
    while n do
      local id = n.id
      if LB and LB.attr then lite(n, s) end
      if id == STYLE then
        s = num(n.style)
      elseif id == ACC and ((s >= 4 or ntxmathotf.design(ntxmathotf.fontsize[node.family_font(fam(), size(s))]) > 1)
          and V.texparams and V.texparams.xheight3 and isext(n) or V.accentxh and n.accent) then
        -- (in a script or at small sizes, where the designs' x-heights differ)
        local r = extaccent(n, s)
        if n == head then head = r end
        list(r.sup, sup(s)); list(r.sub, sub(s))
        n = r
      elseif id == RAD and n.subtype <= 2 then
        local bold, r = boldrad[todirect(n)], n
        boldrad[todirect(n)] = nil
        if s >= 4 and not bold then r = radical(n, s) end
        if r == n then r = exactradical(n, s, bold) end
        if r ~= n then
          if n == head then head = r end
          list(r.sup, sup(s)); list(r.sub, sub(s))
          n = r
        else
          list(n.sup, sup(s)); list(n.sub, sub(s))
        end
      elseif id == NOAD or id == RAD or id == ACC then
        if id == NOAD and n.subtype == 1 and s > 1 then n.subtype = 3 end
        if id == NOAD and (n.subtype == 2 or n.subtype == 1) and s < 4 and n.nucleus
            and n.nucleus.id == MCHAR then
          local t = limits_char(n.nucleus, s)        -- operator set with limits
          if t then n.nucleus.char = t end
        end
        local nu, sb = n.nucleus, tuck(n, s)
        list(nu, (id == RAD or id == ACC) and (s | 1) or s)
        list(n.sup, sup(s)); list(sb, sub(s))
        if id == RAD then list(n.degree, 6) end
      elseif id == FRAC and boldfrac[todirect(n)] then
        -- under \\bm: bm.sty sets the group in the bold version, so TeX builds this fraction
        -- with the bold fonts' rule, num/denom shifts and axis; OpenType keeps its own gaps:
        -- set it here as TeX does (make_fraction)
        local _, wa = table.unpack(boldfrac[todirect(n)])
        boldfrac[todirect(n)] = nil
        local bp = V[wa == 2 and "texparams:heavy" or "texparams:bold"]
        if bp and n.num and n.denom and not n.left and not n.right then
          list(n.num, numer(s)); list(n.denom, numer(s) | 1)
          local u = ntxmathotf.fontsize[node.family_font(fam(), size(s))]
    local z = ntxmathotf.design(u)                     -- (the design of that size, as the .fd files)
          local function sp(v) return math.floor(v * u + 0.5) end
          local function clean(f, st)
            local h
            if f.id == SUBML then h = f.head; f.head = nil
            else h = node.new("noad", 0); h.nucleus = node.copy(f) end
            return node.hpack(node.mlist_to_hlist(h, snames[st], false))
          end
          local x, zb = clean(n.num, numer(s)), clean(n.denom, numer(s) | 1)
          if x.width < zb.width then x = node.hpack(x, zb.width, "exactly")
          elseif zb.width < x.width then zb = node.hpack(zb, x.width, "exactly") end
          local function centre(b, w)             -- TeX's rebox: the narrower one centred
            local g1, g2 = node.new("glue"), node.new("glue")
            g1.stretch, g1.stretch_order, g2.stretch, g2.stretch_order = 65536, 2, 65536, 2
            local inner = b.head; b.head = nil
            local l = g1; g1.next = inner; if inner then inner.prev = g1 end
            local last = node.tail(g1); last.next = g2; g2.prev = last
            node.free(b)
            return node.hpack(l, w, "exactly")
          end
          local w = math.max(x.width, zb.width)
          x, zb = centre(x, w), centre(zb, w)
          local th, axis = sp(bp.rule), sp(bp.axis[z])
          local up = sp(s < 2 and bp.num1[z] or bp.num2[z])
          local down = sp(s < 2 and bp.denom1[z] or bp.denom2[z])
          local clr, delta = s < 2 and 3 * th or th, th // 2
          local d1 = clr - ((up - x.depth) - (axis + delta))
          if d1 > 0 then up = up + d1 end
          local d2 = clr - ((axis - delta) - (zb.height - down))
          if d2 > 0 then down = down + d2 end
          local k1, r, k2 = node.new("kern"), node.new("rule"), node.new("kern")
          k1.kern = (up - x.depth) - (axis + delta)
          r.height, r.depth = th, 0
          k2.kern = (axis - delta) - (zb.height - down)
          x.next, k1.prev = k1, x; k1.next, r.prev = r, k1; r.next, k2.prev = k2, r
          k2.next, zb.prev = zb, k2
          local v = node.vpack(x)
          v.height, v.depth = up + x.height, zb.depth + down
          local nd = tex.nulldelimiterspace
          local b1, b2 = node.new("hlist"), node.new("hlist")
          b1.width, b2.width = nd, nd
          b1.next, v.prev = v, b1; v.next, b2.prev = b2, v
          local box = node.hpack(b1)
          local prev, nxt = n.prev, n.next
          local inner, nu = node.new("noad", 9), node.new("sub_box")
          adopt(box, n); inner.attr, nu.attr = n.attr, n.attr
          nu.head, inner.nucleus = box, nu
          if prev then prev.next = inner; inner.prev = prev end
          if nxt then nxt.prev = inner; inner.next = nxt end
          if n == head then head = inner end
          n.prev, n.next = nil, nil
          node.flush_node(n)
          n = inner
        else
          list(n.num, numer(s)); list(n.denom, numer(s) | 1)
        end
      elseif id == FRAC then
        list(n.num, numer(s)); list(n.denom, numer(s) | 1)
      elseif id == CHOICE then
        n.display = walk(n.display, 0); n.text = walk(n.text, 2)
        n.script = walk(n.script, 4); n.scriptscript = walk(n.scriptscript, 6)
      end
      n = n.next
    end
    return head
  end
  -- a math alphabet whose (text) font lacks a character (\\mathbf{\\delta}): as with TeX's
  -- legacy fonts, a lowercase Greek letter keeps its normal glyph, a capital becomes upright
  -- (bold in a bold alphabet), from the maths font
  local MCH, SML = node.id("math_char"), node.id("sub_mlist")
  local mainfam, hasc, boldf = nil, {}, {}
  local function fontof(fam)
    local fid = node.family_font(fam, 0)
    if not fid or fid == 0 then return nil end
    if hasc[fid] == nil then
      local f = font.getfont(fid) or (fonts.hashes and fonts.hashes.identifiers[fid])
      hasc[fid] = f and f.characters or false
      boldf[fid] = f and f.name and (f.name:lower():find("bold") or f.name:lower():find("demi")
        or f.name:find("%-bx")) and true or false
    end
    return fid
  end
  local function alphafix(h)
    for n in node.traverse(h) do
      for _, fld in ipairs({ "nucleus", "sub", "sup", "num", "denom", "degree" }) do
        local ok, k = pcall(function() return n[fld] end)
        if ok and k then
          if k.id == MCH and k.fam ~= mainfam then
            local fid = fontof(k.fam)
            local ch = fid and hasc[fid]
            local c0 = k.char
            local greek = (c0 >= 0x391 and c0 <= 0x3C9) or (c0 >= 0x1D6A8 and c0 <= 0x1D7C9)
            if ch and not ch[c0] and greek then      -- (Greek only: a Latin letter the alphabet
              local c = k.char                        -- lacks stays missing, as in TeX)
              local cap = (c >= 0x1D6E2 and c <= 0x1D6FA and c - 0x1D6E2) or (c >= 0x391 and c <= 0x3A9 and c - 0x391)
              local m = hasc[fontof(mainfam)] or {}
              -- an OT1 text font (newtxmath's \mathbf) has the eleven capitals TeX puts there
              local ot1 = cap and ntxmathotf.ot1greek and ({ [2] = 0, [3] = 1, [7] = 2, [10] = 3, [13] = 4,
                [15] = 5, [18] = 6, [20] = 7, [21] = 8, [23] = 9, [24] = 10 })[cap]
              local fo = ot1 and font.getfont(fid)
              if ot1 and ch[ot1] and fo and fo.name and fo.name:lower():find("ot1", 1, true) then
                k.char = ot1; goto done
              end
              if cap then
                local b = 0x1D6A8 + cap
                c = (boldf[fid] and m[b]) and b or 0x391 + cap
              end
              if m[c] then k.fam, k.char = mainfam, c end
            end
            ::done::
          elseif k.id == SML then alphafix(k.list) end
        end
      end
      if n.id == node.id("choice") then
        alphafix(n.display); alphafix(n.text); alphafix(n.script); alphafix(n.scriptscript)
      end
    end
  end
  luatexbase.add_to_callback("mlist_to_hlist", function(head, style, penalties)
    if mainfam == nil then                    -- (the family of NewTXMath: unicode-math's own;
      for f = 0, 255 do                       -- looked for until it is there: a formula can come
        local fid = node.family_font(f, 0)    -- before the fonts are set up)
        local fo = fid and fid > 0 and (font.getfont(fid) or fonts.hashes.identifiers[fid])
        if fo and fo.name and fo.name:find("NewTXMath.otf", 1, true) then mainfam = f; break end
      end
    end
    if mainfam then alphafix(head) end
    head = walk(head, num(style))
    return node.mlist_to_hlist(head, style, penalties)
  end, "ntxmath-otf.mlist")
end
-- (Lite: see setlitebm)
-- \\bm, \\hm: the fonts of each math version, as LaTeX records them (read at begin document);
-- a family whose font differs in the bold (heavy) version gets that font as a new family
local BM = { font = {}, alph = {} }
function ntxmathotf.bmfont(v, fam, name)
  BM.font[v] = BM.font[v] or {}
  BM.font[v][fam] = name
end
function ntxmathotf.bmalph(v, cs, enc, name)
  BM.alph[v] = BM.alph[v] or {}
  local function trim(x) return (x:gsub("^%s+", ""):gsub("%s+$", "")) end
  BM.alph[v][cs] = { trim(enc), trim(name) }      -- (robust commands' inner names end in a space)
end
-- (a bold font NFSS has: a family without one (MTPro2 Lite) would only give NFSS's
-- substitution warning and the normal font)
local function defined(cs)      -- (\\csname leaves \\relax behind: not a font shape)
  if not token.is_defined(cs) then return false end
  local c = token.create(cs).cmdname
  return c ~= "relax" and c ~= "undefined_cs"
end
local function shape(spec)
  local enc, fam = spec:match("^([^/]*)/(.*)/[^/]*/[^/]*$")
  if enc and not defined(spec) then                 -- (the family's .fd file, as NFSS loads it)
    local ct = luatexbase.registernumber("catcodetable@atletter")
    tex.runtoks(function()
      tex.sprint(ct, "\\begingroup\\def\\f@encoding{" .. enc .. "}\\def\\f@family{" .. fam
        .. "}\\try@load@fontshape\\endgroup")
    end)
  end
  if defined(spec) then return true end
  for _, w in ipairs({ "bx", "sb", "db", "eb", "ub" }) do
    if defined((spec:gsub("^([^/]*/.*/)[^/]*(/[^/]*)$", "%1" .. w .. "%2"))) then return true end
  end
  return false
end
function ntxmathotf.bmdeclare()
  -- (LaTeX allows 16 symbol fonts, so the new families are not symbol fonts: they count down
  -- from 255, clear of LaTeX's own, and \\bm loads their fonts for the current size)
  local L = ntxmathotf.litebm
  L.attr, L.fams = luatexbase.attributes["MTP@bmattr"], { {}, {} }
  local normal, byspec, top, defs = BM.font.normal or {}, {}, 255, {}
  L.symfam = {}
  for fam, name in pairs(normal) do byspec[name] = byspec[name] or fam; L.symfam[fam] = true end
  for i, v in ipairs({ "bold", "heavy" }) do
    for fam, name in pairs(normal) do
      local b = (BM.font[v] or {})[fam]
      if b and b ~= name and b:match("^[^/]*/.*/[^/]*/[^/]*$") and shape(b) then
        if not byspec[b] then
          byspec[b] = top
          defs[#defs + 1] = string.format("\\MTP@bmfam{%d}{%s}", top, b)
          top = top - 1
        end
        L.fams[i][fam] = byspec[b]
      end
    end
  end
  BM.top = top
  defs[#defs + 1] = "\\directlua{ntxmathotf.bmcheck()}"
  local ct = luatexbase.registernumber("catcodetable@atletter")
  tex.print(ct, "\\gdef\\MTP@bmfams{" .. table.concat(defs) .. "}")
end
-- (LuaTeX takes all math parameters from an OpenType font assigned to a family, so loading
-- the bold fonts would replace the ones in force: keep them)
local MP = { "quad", "axis", "operatorsize", "overbarkern", "overbarrule", "overbarvgap",
  "underbarkern", "underbarrule", "underbarvgap", "radicalkern", "radicalrule", "radicalvgap",
  "radicaldegreebefore", "radicaldegreeafter", "radicaldegreeraise", "stackvgap", "stacknumup",
  "stackdenomdown", "fractionrule", "fractionnumvgap", "fractionnumup", "fractiondenomvgap",
  "fractiondenomdown", "fractiondelsize", "skewedfractionhgap", "skewedfractionvgap",
  "limitabovevgap", "limitabovebgap", "limitabovekern", "limitbelowvgap", "limitbelowbgap",
  "limitbelowkern", "nolimitsubfactor", "nolimitsupfactor", "underdelimitervgap",
  "underdelimiterbgap", "overdelimitervgap", "overdelimiterbgap", "subshiftdrop",
  "supshiftdrop", "subshiftdown", "subsupshiftdown", "subtopmax", "supshiftup", "supbottommin",
  "supsubbottommax", "subsupvgap", "spaceafterscript", "connectoroverlapmin", "primeshiftup",
  "primeshiftdrop", "primespaceafter", "primewidth", "accentbaseheight", "accentbasedepth",
  "flattenedaccentbaseheight", "flattenedaccentbasedepth" }
local MS = { "display", "crampeddisplay", "text", "crampedtext", "script", "crampedscript",
  "scriptscript", "crampedscriptscript" }
local saved
function ntxmathotf.mathparams(save)
  if save then
    saved = {}
    for _, n in ipairs(MP) do
      for _, st in ipairs(MS) do
        local ok, v = pcall(tex.getmath, n, st)
        if ok and v then saved[#saved + 1] = { n, st, v } end
      end
    end
  elseif saved then
    for _, e in ipairs(saved) do tex.setmath("global", e[1], e[2], e[3]) end
    saved = nil
  end
end
-- math alphabets (\\mathrm etc. as NFSS sets them up): a family with the normal font, one
-- with the bold font, and a map from the one to the other by font, for each size
-- a bold version whose font NFSS substitutes with the normal one (no such shape) has no bold:
-- as with bm.sty, that family gets poor man's bold
function ntxmathotf.bmcheck()
  local L = ntxmathotf.litebm
  local function file(id)
    local f = id and id > 0 and font.getfont(id)
    return f and (f.filename or f.name) .. "|" .. tostring(f.size)
  end
  for i = 1, 2 do
    for fam, b in pairs(L.fams[i]) do
      local same = true
      for k = 0, 2 do
        local x, y = node.family_font(fam, k), node.family_font(b, k)
        if x ~= y and file(x) ~= file(y) then same = false end
      end
      if same then L.fams[i][fam] = nil end
    end
  end
end
function ntxmathotf.bmalphabets()
  local L = ntxmathotf.litebm
  local nalph, defs, byspec = BM.alph.normal or {}, {}, {}
  for i, v in ipairs({ "bold", "heavy" }) do
    for cs, e in pairs(BM.alph[v] or {}) do
      local n = nalph[cs]
      -- (unicode-math gives its text alphabets a new font for the normal version only, so
      -- the bold version's entry can be a stale one: then the same font family in bold)
      local nenc, nfam, _, nshape = (n and n[2] or ""):match("^([^/]*)/(.*)/([^/]*)/([^/]*)$")
      local _, bfam = e[2]:match("^([^/]*)/(.*)/([^/]*)/([^/]*)$")
      if nfam and bfam ~= nfam then e = { n[1], string.format("%s/%s/b/%s", nenc, nfam, nshape) } end
      if n and n[2] ~= e[2] and shape(e[2]) then
        for _, spec in ipairs({ n[2], e[2] }) do
          if not byspec[spec] then
            byspec[spec] = BM.top
            defs[#defs + 1] = string.format("\\MTP@bmfam{%d}{%s}", BM.top, spec)
            BM.top = BM.top - 1
          end
        end
        defs[#defs + 1] = string.format("\\directlua{ntxmathotf.bmfontmap(%d,%d,%d)}", i,
          byspec[n[2]], byspec[e[2]])
      end
    end
  end
  local ct = luatexbase.registernumber("catcodetable@atletter")
  tex.print(ct, "\\g@addto@macro\\MTP@bmfams{" .. table.concat(defs) .. "}")
end
function ntxmathotf.bmfontmap(i, nf, bf)
  local L = ntxmathotf.litebm
  L.fontmap = L.fontmap or { {}, {} }
  for k = 0, 2 do
    local id = node.family_font(nf, k)
    if id and id > 0 then L.fontmap[i][id] = bf end
  end
end
-- Lite: letters, Greek and digits under \\bm from newtx (there are no bold MTPro2 fonts)
function ntxmathotf.setlitebm(t)
  local L = ntxmathotf.litebm
  L.it, L.up, L.rm = t.it, t.up, t.rm
  local m = {}
  for i = 0, 25 do
    m[0x1D434 + i] = { "it", 0x41 + i }; m[0x1D44E + i] = { "it", 0x61 + i }
    m[0x30 + (i % 10)] = { "rm", 0x30 + (i % 10) }
  end
  m[0x1D455], m[0x210E] = nil, { "it", 0x68 }    -- (italic h is U+210E)
  -- Greek in TeX's OML order (classic \\epsilon, \\phi are the lunate/straight forms)
  local lc = { 0x0B, 0x0C, 0x0D, 0x0E, 0x22, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x6F, 0x19, 0x1A, 0x26, 0x1B, 0x1C, 0x1D, 0x27, 0x1F, 0x20, 0x21 }
  for i, v in ipairs(lc) do m[0x1D6FC + i - 1] = { "it", v } end
  for cp, v in pairs({ [0x1D715] = 0x40, [0x1D716] = 0x0F, [0x1D717] = 0x23, [0x1D719] = 0x1E,
      [0x1D71A] = 0x25, [0x1D71B] = 0x24, [0x2113] = 0x60, [0x1D6A4] = 0x7B, [0x1D6A5] = 0x7C }) do
    m[cp] = { "it", v }
  end
  -- capital Greek: Greek shapes at TeX's slots 0-10, the others are Latin capitals
  local uc = { "A", "B", 0, 1, "E", "Z", "H", 2, "I", "K", 3, "M", "N", 4, "O", 5, "P", false,
    6, "T", 7, 8, "X", 9, 10 }
  for i, v in ipairs(uc) do
    if v then
      local slot = type(v) == "string" and v:byte() or v
      m[0x0391 + i - 1] = { "up", slot }; m[0x1D6E2 + i - 1] = { "it", slot }
    end
  end
  L.map = m
end
function ntxmathotf.provide(cs, cls)
  local t = token.create(cs)
  local c = t.cmdname
  tex.setcount("MTP@def", (c == "undefined_cs" or c == "math_given" or c == "relax") and 1 or 0)
  -- unicode-math lets many commands be their character (\\therefore = U+2234): keep it, with
  -- the class mtpro2.sty gives the command (TeX's spacing depends on it)
  if cls and (c == "other_char" or c == "letter" or c == "char_given") and t.mode then
    local m = tex.getmathcode(t.mode)
    local cur = m and (m[1] == 7 and 0 or m[1])
    if m and m[1] <= 7 and cur ~= (cls == 7 and 0 or cls) and m[2] then
      tex.setmathcode("global", t.mode, { cls, m[2], m[3] })
    end
  end
end
ntxmathotf.byslot = {}                               -- private code -> glyph name (for \\bm)
function ntxmathotf.glyph(name, cls)
  local s, f = slot(name)
  if s then ntxmathotf.byslot[s] = name end
  if s then tex.sprint(string.format('\\Umathchar"%X"%X"%X ', cls, f, s)) end
end
function ntxmathotf.alpha(set, text)
  if set == "none" then                          -- \\altX outside its alphabet
    texio.write_nl("term and log", "Package ntxmath-otf Warning: invalid use of \\alt" .. text)
    tex.sprint(text)
    return
  end
  local t = V[set] or {}
  local alt = V[set:gsub("alt$", "") .. "alt"] or {}
  local i = 1
  while i <= #text do
    local ch = text:sub(i, i)
    if ch == "\\" then                            -- a command: \\altX is this set's alternate X
      local name = text:match("^%a+", i + 1) or text:sub(i + 1, i + 1)
      i = i + 1 + #name
      while text:sub(i, i) == " " do i = i + 1 end
      local x = name:match("^alt(%a)$")
      if x and alt[x] then ntxmathotf.glyph(alt[x], 0) else tex.sprint("\\" .. name .. " ") end
    else
      if t[ch] then ntxmathotf.glyph(t[ch], 0) elseif ch ~= " " then tex.sprint(ch) end
      i = i + 1
    end
  end
end
-- TeX's per-style parameters (OpenType has one value, scaled by the style's font size)
local styles = { {"display", 0}, {"crampeddisplay", 0}, {"text", 0}, {"crampedtext", 0},
  {"script", 1}, {"crampedscript", 1}, {"scriptscript", 2}, {"crampedscriptscript", 2} }
local fontsize = setmetatable({}, { __index = function(t, id)   -- (font.getfont is slow)
  local f = font.getfont(id); t[id] = f and f.size or 0; return t[id] end })
ntxmathotf.fontsize = fontsize
-- a TFM parameter (in design sizes: a fix_word / 2^20) at a size, as TeX scales it
local scalers = {}
function ntxmathotf.S(v, u)
  local sc = scalers[u]
  if not sc then sc = ntxmathotf.scaler(u); scalers[u] = sc end
  return sc(math.floor(v * 1048576 + 0.5))
end
function ntxmathotf.texparams()
  local p = V.texparams
  if not p then return end
  local S = ntxmathotf.S
  local f, sz = fam(), {}
  for i = 0, 2 do sz[i] = fontsize[node.family_font(f, i)] end
  local function set(name, style, v) tex.setmath(name, style, v) end
  set("supshiftup", "display", S(p.sup1, sz[0]))
  for _, st in ipairs(styles) do
    local s, i = st[1], st[2]
    local u, n = sz[i], sz[math.min(i + 1, 2)]       -- this style's size, its scripts' size
    local lv = ntxmathotf.design(u)                    -- (the design of that size's font)
    local xh = S(p.xheight[lv], u)
    set("supshiftdrop", s, S(p.supdrop, n))
    set("subshiftdrop", s, S(p.subdrop, n))
    set("subsupshiftdown", s, S(p.sub2, u))
    set("fractiondelsize", s, S(s:find("display") and p.delim1 or p.delim2, u))
    set("axis", s, S(p.axis[lv], u))
    set("subtopmax", s, math.abs(xh * 4) // 5)        -- (TeX's integer arithmetic)
    set("supbottommin", s, math.abs(xh) // 4)
    set("supsubbottommax", s, math.abs(xh * 4) // 5)
    if p.rule then set("radicalrule", s, S(p.rule, u)) end
    set("limitabovekern", s, S(p.opspacing5, u))     -- TeX pads limits by big_op_spacing5
    set("limitbelowkern", s, S(p.opspacing5, u))
    tex.setmath("spaceafterscript", s, tex.scriptspace)   -- TeX: \\scriptspace, unscaled
  end
end
-- mtpro2.sty's delimiter tests (\\PEX@, \\SQEX@): TeX's \\lastbox chain on the formula (per
-- level, how many \\lastbox in a row after \\unhbox), the result's depth against box 0's
function ntxmathotf.extest(levels, b, flag)
  local box = tex.box[b]
  local got = box
  local first = true
  for n in levels:gmatch("%d+") do                  -- n \\lastbox in a row, inside the last result
    local items = {}
    for x in node.traverse(got and got.head) do
      if not (first and x.id == node.id("math")) then items[#items + 1] = x end
    end
    first = false
    got = nil
    for _ = 1, tonumber(n) do
      local last = items[#items]                    -- (\\lastbox takes a box, or nothing)
      if last and (last.id == node.id("hlist") or last.id == node.id("vlist")) then
        got = last; items[#items] = nil
      else got = nil; break end
    end
    if not got then break end
  end
  local d0 = tex.box[0] and tex.box[0].depth or 0
  local ct = luatexbase.registernumber("catcodetable@atletter")
  tex.print(ct, (got and got.depth > d0) and "\\global\\" .. flag .. "true" or "\\global\\" .. flag .. "false")
end
-- Tagged PDF (luamml, which runs just after this): characters at private code points, and
-- boxes holding one character (\\xl, \\XL, braces), get the Unicode text of their glyphs
do
  local MC, SB, SM = node.id("math_char"), node.id("sub_box"), node.id("sub_mlist")
  local GL, HL, VL = node.id("glyph"), node.id("hlist"), node.id("vlist")
  local props = node.get_properties_table()
  local touni = {}
  local function uni(fid, c)
    local vc = ntxmathotf.vfchars[fid]
    if vc then                                 -- virtual font: the OpenType glyph's text
      local cmd = vc[c] and vc[c].commands
      cmd = cmd and cmd[#cmd]
      if not (cmd and cmd[1] == "slot") then return nil end
      local u = cmd[3]
      return uni(ntxmathotf.vfbase[fid], u) or (u < 0xF0000 and u) or nil
    end
    local t = touni[fid]
    if not t then
      t = {}; touni[fid] = t
      local f = fonts and fonts.hashes and fonts.hashes.identifiers[fid] or ntxmathotf.basedata[fid]
        or font.getfont(fid)
      for k, ch in pairs(f and f.characters or {}) do
        local u = ch.tounicode
        if type(u) == "string" and #u == 4 then u = tonumber(u, 16)
        elseif type(u) == "string" and #u == 8 then
          local hi, lo = tonumber(u:sub(1, 4), 16), tonumber(u:sub(5), 16)
          u = (hi >= 0xD800 and hi < 0xDC00) and 0x10000 + (hi - 0xD800) * 0x400 + (lo - 0xDC00) or nil
        elseif type(u) ~= "number" then u = nil end
        if u and u ~= k and u ~= 0xFFFD then t[k] = u end
      end
    end
    return t[c]
  end
  local conv
  local function remap(fam, c)
    local fid = node.family_font(fam, 0)
    local u = fid and uni(fid, c)
    if u then conv.register_family(fam, {[c] = u}) end
  end
  local function boxchar(b)                    -- the one character a box shows, if any
    local found
    local function scan(l)
      for x in node.traverse(l) do
        if x.id == GL then
          local u = uni(x.font, x.char)
          if not u and not ntxmathotf.vfchars[x.font] and x.char < 0xF0000 then u = x.char end
          if not u or (found and found ~= u) then return false end
          found = u
        elseif x.id == HL or x.id == VL then
          if scan(x.head) == false then return false end
        end
      end
    end
    if scan(b.head) == false then return nil end
    return found
  end
  local MATH = node.id("math")
  local function boxmath(v)                    -- a vlist with one formula (saved MathML) in a box
    local h = v.head
    if not h or h.next or h.id ~= HL then return nil end
    local m = h.head
    while m and m.id ~= MATH do m = m.next end
    local p = m and props[m]
    local t = p and p.saved_mathml_table
    if not t then return nil end
    -- a copy, keeping only references to nodes in this box: the saved MathML can belong to
    -- a copy of the box that is gone (TeX copies boxes, the properties go with them)
    local here = {}
    local function collect(l)
      for x in node.traverse(l) do
        here[node.direct.todirect(x)] = true
        if x.id == HL or x.id == VL then collect(x.head) end
      end
    end
    collect(v.head)
    local function copy(u)
      if type(u) ~= "table" then return u end
      local c = {}
      for k, x in next, u do
        if k == ":nodes" then
          local ok = true
          for _, n in ipairs(x) do ok = ok and here[node.direct.todirect(n)] end
          if ok then c[k] = x end
        else c[k] = copy(x) end
      end
      return c
    end
    t = copy(t)
    if t[0] == "math" then                     -- (a formula inside a formula: its content)
      t[0], t.xmlns, t["xmlns:tex"], t.display = "mrow", nil, nil, nil
    end
    return t
  end
  local op = {op = true, bin = true, rel = true, open = true, close = true, punct = true}
  local nsub = node.subtypes("noad")
  local walk
  -- \\bm, \\hm (attribute MTP@bmattr, set before luamml runs): the bold character of
  -- Unicode's mathematical alphabets, or mathvariant="bold" for symbols without one
  local BMA
  local function boldcp(u)
    if u >= 0x1D434 and u <= 0x1D467 then return u + 0x34 end        -- italic -> bold italic
    if u == 0x210E then return 0x1D489 end                            -- (italic h)
    if u >= 0x1D6E2 and u <= 0x1D71B then return u + 0x3A end         -- italic Greek
    if u >= 0x41 and u <= 0x5A then return 0x1D400 + u - 0x41 end      -- upright Latin
    if u >= 0x61 and u <= 0x7A then return 0x1D41A + u - 0x61 end
    if u >= 0x30 and u <= 0x39 then return 0x1D7CE + u - 0x30 end      -- digits
    if u >= 0x391 and u <= 0x3A9 then return 0x1D6A8 + u - 0x391 end   -- upright Greek
    if u >= 0x3B1 and u <= 0x3C9 then return 0x1D6C2 + u - 0x3B1 end
    if u == 0x2202 then return 0x1D6DB end                            -- partial
    if u == 0x2207 then return 0x1D6C1 end                            -- nabla
    return nil
  end
  local function bold(k)
    if not (BMA and node.has_attribute(k, BMA)) or props[k] then return end
    props[k] = {mathml_filter = function(mml, core)
      local c = type(mml[1]) == "string" and utf8.len(mml[1]) == 1 and utf8.codepoint(mml[1])
      local b = c and boldcp(c)
      if b then mml[1], mml.mathvariant = utf8.char(b), nil else mml.mathvariant = "bold" end
      return mml, core
    end}
  end
  local function kernel(k, mo)
    if not k then return end
    if k.id == MC then remap(k.fam, k.char); bold(k)
    elseif k.id == SM then walk(k.list, mo)
    elseif k.id == SB and k.list and not props[k] then
      local u = boxchar(k.list)
      if u then props[k] = {mathml_core = {[0] = mo and "mo" or "mi", utf8.char(u)}}
      elseif k.list.id == VL then                -- (\\vcenter{\\hbox{$...$}}: luamml skips vlists)
        local m = boxmath(k.list)
        if m then props[k] = {mathml_table = m} end
      end
    end
  end
  local function delim(d)
    if d and d.small_char ~= 0 then remap(d.small_fam, d.small_char) end
  end
  -- a root with an index (\\MTP@mmlroot): the MathML of the square root, with the index
  ntxmathotf.mmlroot = {}
  local RA
  local function strip(t)          -- (a copy without the nodes: the index box is shown by \\copy)
    if type(t) ~= "table" then return t end
    local c = {}
    for k, v in next, t do
      if not (type(k) == "string" and k:sub(1, 1) == ":") then c[k] = strip(v) end
    end
    return c
  end
  local function root(n, rl)
    local data = (require("luamml-tex-annotate")).data.mathml
    local s, i = data and data["mtp" .. rl], data and data[ntxmathotf.mmlroot[rl] or ""]
    if not s then return end
    data["mtp" .. rl] = nil
    while (s[0] == "mrow" or s[0] == "mstyle" or s[0] == "mtext") and #s == 1 and type(s[1]) == "table" do
      s = s[1]
    end
    if s[0] ~= "msqrt" then return end
    local b = {[0] = "mrow"}
    for k = 1, #s do b[k] = s[k] end
    props[n] = {mathml_table = {[0] = "mroot", b, i and strip(i) or {[0] = "mrow"}}}
  end
  function walk(h, mo)
    for n in node.traverse(h) do
      local t = node.type(n.id)
      local rl = RA and node.has_attribute(n, RA)
      if rl then
        node.unset_attribute(n, RA)
        if rl >= 0x40000000 then props[n] = {mathml_table = {[0] = "mrow"}} else root(n, rl) end
      end
      local m = mo or (t == "noad" and op[(nsub[n.subtype] or ""):gsub("^op.*", "op")])
      if t == "noad" or t == "accent" or t == "radical" then
        kernel(n.nucleus, m); kernel(n.sub, false); kernel(n.sup, false)
        if t == "accent" then kernel(n.accent, true); kernel(n.bot_accent, true) end
        if t == "radical" then delim(n.left); kernel(n.degree, false) end
      elseif t == "fraction" then
        kernel(n.num, false); kernel(n.denom, false); delim(n.left); delim(n.right)
      elseif t == "fence" then delim(n.delim)
      elseif t == "choice" then
        walk(n.display); walk(n.text); walk(n.script); walk(n.scriptscript)
      end
    end
  end
  function ntxmathotf.mathml()
    local ok, c = pcall(require, "luamml-convert")
    if not ok or not luatexbase.in_callback("pre_mlist_to_hlist_filter", "luamml.to_mathml") then return end
    conv = c
    RA = luatexbase.attributes["MTP@mmlattr"]
    BMA = luatexbase.attributes["MTP@bmattr"]
    luatexbase.add_to_callback("pre_mlist_to_hlist_filter", function(head)
      walk(head); return true
    end, "ntxmathotf.mathml")
    luatexbase.declare_callback_rule("pre_mlist_to_hlist_filter", "ntxmathotf.mathml", "before", "luamml.to_mathml")
  end
end
-- the MathML of a construct of mtpro2.sty's (\\MTP@mml): Lua source for luamml's annotation
do
  local fences = { ["("] = "(", [")"] = ")", ["["] = "[", ["]"] = "]", ["<"] = "\u{27E8}",
    [">"] = "\u{27E9}", ["/"] = "/", ["|"] = "|", ["\\langle"] = "\u{27E8}", ["\\rangle"] = "\u{27E9}",
    ["\\backslash"] = "\\", ["\\lbrace"] = "{", ["\\rbrace"] = "}", ["\\{"] = "{", ["\\}"] = "}",
    ["\\lcbrace"] = "{", ["\\rcbrace"] = "}", ["\\|"] = "\u{2016}", ["\\vert"] = "|", ["\\Vert"] = "\u{2016}",
    ["\\lbrack"] = "[", ["\\rbrack"] = "]", ["\\lfloor"] = "\u{230A}", ["\\rfloor"] = "\u{230B}",
    ["\\lceil"] = "\u{2308}", ["\\rceil"] = "\u{2309}" }
  local function str(s) return string.format("%q", s) end
  local function mo(d)
    local c = fences[(d:gsub("%s+$", ""))]
    return c and string.format("{[0]='mo', fence='true', stretchy='true', lspace='0', rspace='0', %s}, ", str(c)) or ""
  end
  function ntxmathotf.mml(lab, kind, a, b)
    local arg = string.format("consume_label(%s) or {[0]='mrow'}", str(lab))
    local src
    if kind == "fence" then
      src = "mathml = {[0]='mrow', " .. mo(a) .. arg .. ", " .. mo(b) .. "}"
    elseif kind == "fence0" then           -- (the argument is a phantom: dropped)
      src = "mathml = (function() local _ = " .. arg .. " return {[0]='mrow', " .. mo(a) .. mo(b) .. "} end)()"
    elseif kind == "over" or kind == "under" then
      src = string.format("nucleus = true, mathml = {[0]='m%s', %s, {[0]='mo', stretchy='true', %s}}",
        kind, arg, str(kind == "over" and "\u{23DE}" or "\u{23DF}"))
    elseif kind == "sqrt" then
      src = "mathml = {[0]='msqrt', " .. arg .. "}"
    end
    tex.sprint(-2, src or "")
  end
end
-- unicode-math's symbol commands whose character MTPro2 lacks: before unicode-math loads,
-- savemissing() keeps the definitions packages already gave them (amsmath's \\iiiint,
-- \\varTheta); when the document starts, nochar() restores those, and makes the others an
-- error instead of a blank (with the Type 1 fonts they are mostly undefined)
function ntxmathotf.savemissing()
  local ct = luatexbase.registernumber("catcodetable@atletter")
  for cs in pairs(V.missing or {}) do
    if token.is_defined(cs) then
      local c = token.create(cs).cmdname
      if c ~= "relax" and c ~= "undefined_cs" then tex.print(ct, "\\let\\MTP@s@" .. cs .. "\\" .. cs) end
    end
  end
end
function ntxmathotf.nochar()
  local ct = luatexbase.registernumber("catcodetable@atletter")
  for cs, cp in pairs(V.missing or {}) do
    local t = token.create(cs)
    local c, m = t.cmdname, t.mode
    local ch
    if c == "math_given" or c == "xmath_given" then
      ch = type(m) == "table" and m[#m] or (type(m) == "number" and m % 0x200000) or nil
    elseif c == "other_char" or c == "letter" then      -- (\\let to the character itself:
      local mc = tex.getmathcode(m)                    -- its mathcode names it, or makes it
      ch = type(mc) == "table" and (mc[3] == m or mc[1] == 8) and m or nil   -- active: operators)
    end
    do
      if ch == cp then
        if token.is_defined("MTP@s@" .. cs) then
          tex.print(ct, "\\let\\" .. cs .. "\\MTP@s@" .. cs)
        else
          tex.print(ct, string.format("\\protected\\def\\%s{\\MTP@nochar{%s}{%04X}}", cs, cs, cp))
        end
      end
    end
  end
end
-- a composite symbol (a macro): its definition inside \\MTP@actual (\\DOTSB first, for
-- amsmath's \\dots)
function ntxmathotf.vargreek()
  local ct = luatexbase.registernumber("catcodetable@atletter")
  for n, k in pairs({ Gamma = 2, Delta = 3, Theta = 7, Lambda = 10, Xi = 13, Pi = 15, Sigma = 18,
                      Upsilon = 20, Phi = 21, Psi = 23, Omega = 24 }) do
    local m = tex.getmathcode(0x391 + k)
    local fam = type(m) == "table" and m[2] or 0
    tex.print(ct, string.format("\\Umathchardef\\var%s=7 %d %d\\relax", n, fam, 0x1D6E2 + k))
  end
end
function ntxmathotf.composite(cs, hex)
  local t = token.create(cs)
  if not t.cmdname:find("call") then return end
  local ct = luatexbase.registernumber("catcodetable@atletter")
  -- an inner atom (\\cdots) keeps the span inside it: after a line break at a preceding
  -- binary operator the space before the atom must still be discarded
  local body = token.get_macro(cs) or ""
  if body:find("^%s*\\protect") then body = token.get_macro(cs .. " ") or "" end
  local a, b = "", ""
  if body:find("^%s*\\mathinner%s*{") then a, b = "\\mathinner{", "}" end
  tex.print(ct, string.format("\\expandafter\\let\\csname MTP@c@%s\\endcsname\\%s"
    .. "\\def\\%s{\\csname DOTSB\\endcsname%s\\MTP@actual{%s}{\\MTP@nested\\csname MTP@c@%s\\endcsname"
    .. "\\MTP@unnested}%s}", cs, cs, cs, a, hex, cs, b))
end
-- hyperref's PDF strings (bookmarks) of headings with maths: unicode-math's symbol commands
-- as their characters (as tokens they stop \\pdfstringdef), alphabets and \\bm as their argument
local umtable
function ntxmathotf.pdfstr()
  if not umtable then
    umtable = {}
    local p = kpse.find_file("unicode-math-table.tex", "tex")
    local fh = p and io.open(p)
    if fh then
      for cp, cs in fh:read("a"):gmatch('\\UnicodeMathSymbol{"(%x+)}{\\(%a+)%s*}') do
        umtable[#umtable + 1] = { cs, tonumber(cp, 16) }
      end
      fh:close()
    end
  end
  local ct = luatexbase.registernumber("catcodetable@atletter")
  local out = {}
  for _, e in ipairs(umtable) do
    local c = token.is_defined(e[1]) and token.create(e[1]).cmdname
    if c == "math_given" or c == "xmath_given" or c == "other_char" or c == "letter" then
      out[#out + 1] = string.format("\\def\\%s{\\Uchar\"%X }", e[1], e[2])
    end
  end
  tex.sprint(ct, table.concat(out))
end
-- mtpro2.sty's accents without a code point of their own (\\dotup, \\what, ...)
function ntxmathotf.accent(name)
  local g, s, f = (V.accent or {})[name]
  if g then s, f = slot(g) end
  if s and f then tex.sprint(string.format('\\Umathaccent"0"%X"%X ', f, s)) end
end
function ntxmathotf.accents()
  local ct = luatexbase.registernumber("catcodetable@atletter")
  for name in pairs(V.accent or {}) do
    tex.print(ct, string.format("\\DeclareRobustCommand\\%s{\\directlua{ntxmathotf.accent('%s')}}",
      name, name))
  end
end
function ntxmathotf.delim(set, key, cls)
  local g = (V[set] or {})[key]
  if not g then return end
  local s, f = slot(g)
  if s then tex.sprint(string.format('\\Udelimiter"%X"%X"%X ', cls, f, s)) end
end
