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
