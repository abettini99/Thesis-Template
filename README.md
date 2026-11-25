# Table header Scope through attribute classes: test files

Four minimal tagged LaTeX documents, each with one three-column table whose first row is a header row
(`tagging-setup={table/header-rows=1}`). They use only LaTeX itself (`article` class, `array`); they
differ only in the PDF version and in where the header cells' Scope is:

| File | PDF version | Scope |
|---|---|---|
| scope1 | 1.7, PDF/UA-1 | as LaTeX writes it: through an attribute class (`/C /TH-col`, in the ClassMap) |
| scope2 | 2.0, PDF/UA-2 | as LaTeX writes it: through an attribute class |
| scope3 | 2.0, PDF/UA-2 | the class, and also on the cell itself (`/A << /O /Table /Scope /Column >>`) |
| scope4 | 1.7, PDF/UA-1 | the class, and also on the cell itself |

scope3 and scope4 add the `/A` entry with a few lines in the preamble (wrapping `\__tag_struct_write_obj:n`).
The PDFs are built on GitHub from these sources in the official TeX Live image: see BUILD.txt.
