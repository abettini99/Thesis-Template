-- Hyphenation log for tools/check_hyphenation.py (LuaLaTeX).
-- After TeX has broken a paragraph into lines, every line that ends in a hyphen TeX added (not the
-- hyphen of a compound such as "well-known") is recorded: the two halves of the word, and, when the
-- page is shipped out, the PDF page of each half. Only the log changes, never the output.
local GLYPH, DISC, HLIST, KERN = node.id("glyph"), node.id("disc"), node.id("hlist"), node.id("kern")
local MARGINKERN = node.id("margin_kern")
local EXPLICIT, AUTOMATIC = 1, 2      -- disc subtypes of a typed "-" (a compound word)
local count, para = 0, 0

local function chars(n, out)          -- the text of a glyph, ligatures unpacked
  if n.components then
    for c in node.traverse(n.components) do chars(c, out) end
  elseif n.char and n.char > 0 and n.char < 0xF0000 then
    out[#out + 1] = utf8.char(n.char)
  end
end

local function word_before(n)         -- letters before node n, back to the previous space; and
  local out = {}                      -- whether the word starts a sentence ("start") or not ("mid")
  while n and (n.id == GLYPH or n.id == DISC or n.id == KERN) do
    if n.id == GLYPH then
      local c = {}
      chars(n, c)
      for i = #c, 1, -1 do table.insert(out, 1, c[i]) end
    end
    n = n.prev
  end
  while n and n.id ~= GLYPH do n = n.prev end
  local prev = n and n.char and n.char < 0xF0000 and utf8.char(n.char) or ""
  local start = (prev == "" or prev:match("[%.%?!:]")) and "start" or "mid"
  return table.concat(out), start
end

local function word_after(n)          -- letters from the start of a line up to the first space
  while n and n.id ~= GLYPH do
    if n.id == node.id("glue") and n.width ~= 0 and n.subtype == 0 then return "" end
    n = n.next
  end
  local out = {}
  while n and (n.id == GLYPH or n.id == DISC or n.id == KERN) do
    if n.id == GLYPH then chars(n, out) end
    n = n.next
  end
  return table.concat(out)
end

local function mark(text)             -- a late_lua node that logs the PDF page when shipped out
  local n = node.new("whatsit", "late_lua")
  n.data = function() texio.write_nl("log", text .. " " .. (status.total_pages + 1) .. ";") end
  return n
end

luatexbase.add_to_callback("post_linebreak_filter", function(head)
  para = para + 1
  local line_no, pending = 0, nil
  for line in node.traverse_id(HLIST, head) do
    line_no = line_no + 1
    if pending then                   -- second half of the word broken at the end of the last line
      texio.write_nl("log", string.format("Thesis hyphen %d after: %s;", pending, word_after(line.head)))
      line.head = node.insert_before(line.head, line.head, mark("Thesis hyphen " .. pending .. " page2"))
      pending = nil
    end
    local t = node.tail(line.head)
    while t and t.id ~= DISC and t.id ~= GLYPH do t = t.prev end
    local hy = t and t.prev
    while hy and (hy.id == MARGINKERN or hy.id == KERN) do hy = hy.prev end   -- microtype protrusion
    if t and t.id == DISC and t.subtype ~= EXPLICIT and t.subtype ~= AUTOMATIC
       and hy and hy.id == GLYPH and hy.char == 0x2D then
      count = count + 1
      local before, start = word_before(hy.prev)
      texio.write_nl("log", string.format("Thesis hyphen %d para %d line %d %s before: %s;",
                                          count, para, line_no, start, before))
      node.insert_after(line.head, t, mark("Thesis hyphen " .. count .. " page1"))
      pending = count
    end
  end
  return true
end, "thesis.hyphenationlog")
