-- Tagged PDF: equation numbers of split equations in the MathML (read by tagging.tex).
--
-- In \begin{equation}\begin{split} ... \end{split}\end{equation}, LaTeX's tagging code keeps
-- only the split's own table in the MathML. The row that holds the equation number is
-- dropped, so the number goes missing from the MathML and its structure element is left
-- without a parent ("Structure ... has 1 kids but no parent"). Here the number is kept back
-- when it is made, and added again around the split's table, as luamml does for an equation.

local properties = node.get_properties_table()
local to_text = require'luamml-lr'

local pending_tag

local function new_command(name, func, flags)
  local id = luatexbase.new_luafunction(name)
  if flags then token.set_lua(name, id, flags) else token.set_lua(name, id) end
  lua.get_functions_table()[id] = func
end

-- \thesis@luamml@savetag <struct num>: in place of luamml's own save, in an equation with split.
new_command('thesis@luamml@savetag', function()
  local struct_num = token.scan_int()
  local tag = to_text(tex.nest.top.head)
  tag[':structnum'] = struct_num
  pending_tag = tag
end, 'protected')

-- \thesis@luamml@wraptag: right after luamml has attached the split's table to the vcenter.
new_command('thesis@luamml@wraptag', function()
  local tag = pending_tag
  pending_tag = nil
  if not tag then return end
  local tail = tex.nest.top.tail
  local nucleus = tail and tail.nucleus
  local props = nucleus and properties[nucleus]
  local inner = props and props.mathml_table
  if not inner then return end
  props.mathml_table = { [0] = 'mtable',
    displaystyle = 'true',
    intent = ':system-of-equations',
    { [0] = 'mtr',
      { [0] = 'mtd', intent = ':equation-label', tag },
      { [0] = 'mtd', intent = ':pause-medium', inner },
    },
  }
end, 'protected')

-- Numbers and upright words in the MathML as one element. siunitx sets 6.02214076 as 6{.}022\,140\,76: a digit, a
-- decimal marker in braces and groups of digits with thin spaces between them. luamml made each of
-- them its own element (<mn>6</mn> <mo>.</mo> <mn>022</mn> <mspace/> <mn>140</mn> ...), which is
-- read as several numbers or as a product. Before luamml converts a formula, a run of digits, decimal
-- points between digits and thin spaces between digits gets one <mn> with all the digits on its first
-- element; the others give nothing. Likewise a run of upright letters (\mathrm{disc}) becomes one <mi>,
-- not four. The typeset formula does not change.
local noad_id, glue_id, kern_id = node.id'noad', node.id'glue', node.id'kern'
local sub_mlist_id, math_char_id, choice_id = node.id'sub_mlist', node.id'math_char', node.id'choice'
local ord = 0                      -- (an ordinary noad)
local thin = 3 * 65536             -- \thinmuskip, 3mu, as math glue holds it

-- the character of an ordinary noad without scripts, also when it is in braces ({.})
local function char_of(n)
  if n.id ~= noad_id or n.subtype ~= ord or n.sub or n.sup then return nil end
  local nuc = n.nucleus
  if not nuc then return nil end
  if nuc.id == math_char_id then return nuc.char end
  if nuc.id == sub_mlist_id and nuc.head and not nuc.head.next then return char_of(nuc.head) end
end
local function is_digit(c) return c and c >= 48 and c <= 57 end
-- with unicode-math, a letter in maths is a mathematical letter (U+1D400 and on); a plain ASCII letter
-- comes from \mathrm, \mathsf or the like: upright text
local function is_letter(c) return c and ((c >= 65 and c <= 90) or (c >= 97 and c <= 122)) end
-- a letter directly in the list, not in braces of its own: \mathrm{disc} is one group of four letters,
-- \mathsf{B}\mathsf{v} two groups of one (a product, not a word)
local function letter_of(n)
  local c = char_of(n)
  if is_letter(c) and n.nucleus.id == math_char_id then return c end
end
local function is_thin(n)
  return (n.id == glue_id and n.width == thin and n.stretch == 0 and n.shrink == 0)
      or (n.id == kern_id and n.kern == thin)
end

-- a box with nothing to read in it (no character, no rule): a link target that hyperref raises
-- above an equation, a strut, an empty \hbox{}. luamml wrote it as <mtext> around a whole <math> of
-- its own (a <math> inside a <math>); it gives nothing now.
local glyph_id, hlist_id, vlist_id, rule_id = node.id'glyph', node.id'hlist', node.id'vlist', node.id'rule'
local sub_box_id = node.id'sub_box'
local function readable(head)
  for m in node.traverse(head) do
    if m.id == glyph_id or (m.id == rule_id and m.width > 0 and m.height + m.depth > 0) then return true end
    if (m.id == hlist_id or m.id == vlist_id) and readable(m.list) then return true end
  end
  return false
end

-- the MathML of one element of a run: on the nucleus of a noad, so that luamml still spaces the noad
-- as an ordinary symbol (the space after "=" stays); on a thin space itself
local function give(n, t)
  local target = n.id == noad_id and n.nucleus or n
  properties[target] = properties[target] or {}
  properties[target].mathml_table = t
end

local merge_list
local function merge_fields(n)
  for _, f in ipairs{ 'nucleus', 'sub', 'sup', 'num', 'denom', 'degree' } do
    local ok, v = pcall(function() return n[f] end)
    if ok and v and v.id == sub_mlist_id then merge_list(v.head) end
  end
  if n.id == choice_id then
    for _, f in ipairs{ 'display', 'text', 'script', 'scriptscript' } do merge_list(n[f]) end
  end
end

function merge_list(head)
  local n = head
  while n do
    merge_fields(n)
    if n.id == noad_id and n.subtype == ord and not n.sub and not n.sup and n.nucleus
      and n.nucleus.id == sub_box_id and not readable(n.nucleus.list) then
      properties[n] = properties[n] or {}
      properties[n].mathml_table = properties[n].mathml_table or { [0] = 'mrow' }
    end
    if is_digit(char_of(n)) then
      -- the run: digits, and '.' or thin spaces with digits on both sides
      local run, text, m = { n }, utf8.char(char_of(n)), n.next
      local joined = false
      while m do
        local c = char_of(m)
        if is_digit(c) then
          run[#run + 1], text, m = m, text .. utf8.char(c), m.next
        elseif (c == 46 or is_thin(m)) and m.next and is_digit(char_of(m.next)) then
          run[#run + 1] = m
          if c == 46 then text = text .. '.' end
          joined, m = true, m.next
        else
          break
        end
      end
      if joined then
        give(run[1], { [0] = 'mn', text })
        for i = 2, #run do give(run[i], { [0] = 'mrow' }) end
      end
      n = m
    elseif letter_of(n) then
      -- a word in upright letters (\mathrm{disc}, u_\mathrm{eff}): one <mi>, read as a word, not
      -- letter by letter
      local run, text, m = { n }, utf8.char(letter_of(n)), n.next
      while m and letter_of(m) do
        run[#run + 1], text, m = m, text .. utf8.char(letter_of(m)), m.next
      end
      if #run > 1 then
        give(run[1], { [0] = 'mi', text })
        for i = 2, #run do give(run[i], { [0] = 'mrow' }) end
      end
      n = m
    else
      n = n.next
    end
  end
end

luatexbase.add_to_callback('pre_mlist_to_hlist_filter', function(head)
  merge_list(head)
  return true
end, 'thesis.numbers')
luatexbase.declare_callback_rule('pre_mlist_to_hlist_filter', 'thesis.numbers', 'before', 'luamml.to_mathml')
