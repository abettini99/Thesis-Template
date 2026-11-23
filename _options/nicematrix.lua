-- Tagged PDF: the MathML of nicematrix matrices (read by nicematrix.tex).
--
-- nicematrix draws its matrices with PGF, so the MathML that luamml makes of them is empty.
-- nicematrix.tex therefore sets the same entries once more, out of sight, as an amsmath
-- matrix, and saves its MathML. Here that MathML is made to say what the reader sees:
--   * the labels outside the matrix (first-row, last-row, first-col, last-col) are taken out
--     of the table, so that it keeps its real size, and named in a note after the matrix;
--   * a \Block with an entry becomes one cell spanning its rows and columns (rowspan,
--     columnspan), boxed (menclose) if the block is drawn;
--   * a brace over or under the full width of the matrix becomes a MathML brace (mover,
--     munder) with its label; braces over part of it, \SubMatrix delimiters and frames
--     around several entries are named in the note, as "brace over row 1, columns 1 to 2:
--     first two".
-- Colours and fills are left out: they only emphasise, and the text says what they mark.

local annotate_env = require'luamml-tex-annotate'

local words = {
  en = {
    columns = 'columns', rows = 'rows', row = 'row', column = 'column', to = 'to',
    over = 'brace over', under = 'brace under', box = 'box around',
    delims = { p = 'parentheses around', b = 'brackets around', B = 'braces around',
               v = 'vertical bars around', V = 'double vertical bars around' },
  },
  nl = {
    columns = 'kolommen', rows = 'rijen', row = 'rij', column = 'kolom', to = 'tot en met',
    over = 'accolade boven', under = 'accolade onder', box = 'kader om',
    delims = { p = 'haakjes om', b = 'blokhaken om', B = 'accolades om',
               v = 'verticale strepen om', V = 'dubbele verticale strepen om' },
  },
}

local function find(el, name)
  if type(el) ~= 'table' then return end
  if el[0] == name then return el end
  for _, child in ipairs(el) do
    local found = find(child, name)
    if found then return found, el end
  end
end

-- the marker that nicematrix.tex puts in a cell for a \Block
local function take_marker(cell)
  for i, child in ipairs(cell) do
    if type(child) == 'table' and child['thesis-span'] then
      table.remove(cell, i)
      return child
    end
    local found = type(child) == 'table' and take_marker(child)
    if found then return found end
  end
end

local function range(w, a, b, singular, plural)
  if a == b then return singular .. ' ' .. a end
  return plural .. ' ' .. a .. ' ' .. w.to .. ' ' .. b
end

local function text(s) return {[0] = 'mtext', s} end

-- spec: lang, first_row, last_row, first_col, last_col (booleans),
--       notes = list of {kind = 'over'|'under'|'p'|'b'|..., from = 'i-j', to = 'k-l', label = mathml}
function annotate_env.thesis_nicematrix(mathml, spec)
  if not mathml then return {[0] = 'mrow'} end
  local w = words[spec.lang] or words.en
  local tbl = find(mathml, 'mtable')
  if not tbl then return mathml end

  -- rows of the table; every cell has a marker (nicematrix.tex), so that none is left out
  local function strip_cell_markers(el)
    for k = #el, 1, -1 do
      local child = el[k]
      if type(child) == 'table' then
        if child['thesis-cell'] then table.remove(el, k) else strip_cell_markers(child) end
      end
    end
  end
  local rows = {}
  for _, child in ipairs(tbl) do
    if type(child) == 'table' and child[0] == 'mtr' then
      rows[#rows + 1] = child
      for _, cell in ipairs(child) do strip_cell_markers(cell) end
    end
  end
  -- (a \\ at the end makes a last row of one empty cell)
  local last = rows[#rows]
  if last and #last == 1 and #last[1] == 0 then table.remove(rows) end
  local ncols = 0
  for _, r in ipairs(rows) do ncols = math.max(ncols, #r) end

  -- labels outside the matrix
  local col_labels, row_labels = {}, {}
  -- (a label is kept with its position; a missing one as false)
  local function cells_of(r, from, to)
    local out = {}
    for c = from, to do
      local cell = r[c]
      out[#out + 1] = cell and #cell > 0 and {[0] = 'mrow', table.unpack(cell)} or false
    end
    return out
  end
  local first_c = spec.first_col and 2 or 1
  local last_c = spec.last_col and ncols - 1 or ncols
  if spec.first_row and rows[1] then
    for _, l in ipairs(cells_of(rows[1], first_c, last_c)) do col_labels[#col_labels + 1] = l end
    table.remove(rows, 1)
  end
  if spec.last_row and #rows > 0 then
    for _, l in ipairs(cells_of(rows[#rows], first_c, last_c)) do col_labels[#col_labels + 1] = l end
    table.remove(rows)
  end
  for _, r in ipairs(rows) do
    if spec.last_col then
      row_labels[#row_labels + 1] = cells_of(r, ncols, ncols)[1]
      if #r >= ncols then table.remove(r, ncols) end
    end
    if spec.first_col then
      row_labels[#row_labels + 1] = cells_of(r, 1, 1)[1]
      table.remove(r, 1)
    end
    for c = #r + 1, last_c - first_c + 1 do r[c] = {[0] = 'mtd'} end
  end
  local nrows, nc = #rows, last_c - first_c + 1

  -- blocks
  local notes = {}
  local covered = {}
  for i, r in ipairs(rows) do
    for j, cell in ipairs(r) do
      local marker = take_marker(cell)
      if marker then
        local h, v = marker['thesis-span']:match'^([%d*]+)-([%d*]+)$'
        h = h == '*' and nrows - i + 1 or tonumber(h) or 1
        v = v == '*' and nc - j + 1 or tonumber(v) or 1
        local drawn = marker['thesis-draw'] == 'true'
        if #marker > 0 then
          -- a block with an entry: one cell over its rows and columns
          local content = {[0] = 'mrow', table.unpack(marker)}
          for k = #cell, 1, -1 do cell[k] = nil end
          cell[1] = drawn and {[0] = 'menclose', notation = 'box', content} or content
          if h > 1 then cell.rowspan = tostring(h) end
          if v > 1 then cell.columnspan = tostring(v) end
          for a = i, i + h - 1 do
            for b = j, j + v - 1 do
              if a ~= i or b ~= j then covered[a .. ',' .. b] = true end
            end
          end
        elseif drawn then
          -- a frame around entries of their own
          notes[#notes + 1] = {text(w.box .. ' ' .. range(w, i, i + h - 1, w.row, w.rows)
            .. ', ' .. range(w, j, j + v - 1, w.column, w.columns))}
        end
      end
    end
  end
  for i, r in ipairs(rows) do
    for j = #r, 1, -1 do
      if covered[i .. ',' .. j] then table.remove(r, j) end
    end
  end
  -- the table gets the rows that are left
  for k = #tbl, 1, -1 do tbl[k] = nil end
  for k, r in ipairs(rows) do tbl[k] = r end

  -- braces and sub-matrices
  local result = mathml
  for _, n in ipairs(spec.notes or {}) do
    local i1, j1 = n.from:match'^(%d+)-(%d+)$'
    local i2, j2 = n.to:match'^(%d+)-(%d+)$'
    i1, j1, i2, j2 = tonumber(i1), tonumber(j1), tonumber(i2), tonumber(j2)
    if i1 and j1 and i2 and j2 then
      local label = n.label or {[0] = 'mrow'}
      if (n.kind == 'over' or n.kind == 'under') and j1 == 1 and j2 == nc then
        if n.kind == 'over' then
          result = {[0] = 'mover', {[0] = 'mover', result, {[0] = 'mo', stretchy = 'true', '⏞'}}, label}
        else
          result = {[0] = 'munder', {[0] = 'munder', result, {[0] = 'mo', stretchy = 'true', '⏟'}}, label}
        end
      else
        local what = (n.kind == 'over' and w.over) or (n.kind == 'under' and w.under)
          or w.delims[n.kind]
        if what then
          local where = what .. ' ' .. range(w, i1, i2, w.row, w.rows) .. ', '
            .. range(w, j1, j2, w.column, w.columns)
          if #label > 0 then
            notes[#notes + 1] = {text(where .. ': '), label}
          else
            notes[#notes + 1] = {text(where)}
          end
        end
      end
    end
  end

  -- the labels, then the other notes, after the matrix
  -- "columns: x, y, z", or with a label missing "row 1: momentum, row 3: continuity"
  local function list(plural, singular, items)
    local complete, any = true, false
    for _, item in ipairs(items) do
      if item then any = true else complete = false end
    end
    if not any then return end
    local out, first = {complete and text(plural .. ': ') or nil}, true
    for k, item in ipairs(items) do
      if item then
        if not first then out[#out + 1] = text(', ') end
        first = false
        if not complete then out[#out + 1] = text(singular .. ' ' .. k .. ': ') end
        out[#out + 1] = item
      end
    end
    return out
  end
  local rl, cl = list(w.rows, w.row, row_labels), list(w.columns, w.column, col_labels)
  if rl then table.insert(notes, 1, rl) end
  if cl then table.insert(notes, 1, cl) end
  if #notes == 0 then return result end
  local out = {[0] = 'mrow', result, text(' (')}
  for k, note in ipairs(notes) do
    if k > 1 then out[#out + 1] = text('; ') end
    for _, part in ipairs(note) do out[#out + 1] = part end
  end
  out[#out + 1] = text(')')
  return out
end
