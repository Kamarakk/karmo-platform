# Module 06 · Structured output

**Time:** 35 minutes · **Course reference:** `code/02-ai-workflows/06-structured-outputs/main.py` and `07-structured-outputs-pydantic/`

**The idea:** Give Ollama a JSON schema in the `format` field and it must return matching JSON. Then **your code** checks the math before anything is saved. The model extracts; code verifies.

## Steps

**1. Read the sample invoice.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/06-structured-output/invoice_good.txt
```
You should see line items that add up to $385 plus $60 shipping, total $445.

**2. Extract it into JSON and save it.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/06-structured-output && python3 extract_invoice.py invoice_good.txt
```
You should see a JSON object with `vendor_name`, `line_items`, `shipping`, `total_shown`, `total`, then `SAVED to .../invoices.db`.

**3. Run it on an invoice with no total.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/06-structured-output && python3 extract_invoice.py invoice_broken.txt
```
You should see `REJECTED, nothing saved:` with a reason. The model can't slip a guessed total past the code check.

**4. Look at what got saved.**
```bash
sqlite3 ~/Desktop/KARMO-AI-Course/labs/06-structured-output/invoices.db "select * from invoices;"
```
You should see one row: the good invoice only.

**5. Find the schema and validator in the code.**
```bash
grep -nE "SCHEMA|def validate" ~/Desktop/KARMO-AI-Course/labs/06-structured-output/extract_invoice.py
```
You should see where the schema is defined and where the math is checked.

**6. Try a real supplier invoice.** Copy the text of one of your plant invoices into `mine.txt` in the same folder, then run:
```bash
cd ~/Desktop/KARMO-AI-Course/labs/06-structured-output && python3 extract_invoice.py mine.txt
```
You should see either `SAVED` or a clear rejection reason.

## Done when
- [ ] The good invoice saved and the broken one was rejected
- [ ] You can point to the line where code, not the model, checks the total

**Durable:** schema in, validation after, never trust unchecked numbers. **Perishable:** the exact `format` API.
