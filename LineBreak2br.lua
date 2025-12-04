-- Emit <br>\n in markdown for hard line break
function LineBreak()
  return pandoc.RawInline('markdown', '<br>\r') -- \n here would become \n\n in markdown, but \r ends up \n
end
