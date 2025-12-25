# Database Commit Flow in catprint

## How Changes Are Saved to Database

### 1. update_person() Function Flow
Location: [src/catprint/utils.py](src/catprint/utils.py#L513-L522)

```python
# Step 1: Execute UPDATE query
c.execute(
    "UPDATE people SET name = ?, max_clearance = ?, password = ?, position = ?, is_admin = ?, pokeball_count = ?, jobs = ?, companies = ? WHERE id = ?",
    (new_name, new_max, new_pw, new_pos, new_admin, new_pok, 
     _json.dumps(new_jobs, ensure_ascii=False), 
     _json.dumps(new_companies or {}, ensure_ascii=False), 
     str(person_id)),
)

# Step 2: COMMIT changes to disk
conn.commit()  # <--- THIS LINE SAVES EVERYTHING TO DATABASE

# Step 3: Close connection
conn.close()

# Step 4: Return success
return True
```

### 2. Jobs Derivation Logic
Location: [src/catprint/utils.py](src/catprint/utils.py#L498-L511)

When companies are updated, jobs are automatically derived:

```python
if companies is not None:
    # Extract ALL positions from ALL companies
    all_positions = []
    for company_positions in new_companies.values():
        if company_positions:
            all_positions.extend(company_positions)
    
    # Remove duplicates and sort
    new_jobs = sorted(list(set(all_positions)))
    
    # Non-admins with no positions get default "Barista"
    if not new_admin and not new_jobs:
        new_jobs = ["Barista"]
```

### 3. Verification After Save
Location: [app.py](app.py#L871-L882)

After saving companies in DB viewer:

```python
ok = utils.update_person(rec['id'], companies=new_companies)
if ok:
    # Read DIRECTLY from DB to verify save
    import sqlite3, json
    fresh_conn = sqlite3.connect(str(utils.DEFAULT_PEOPLE_DB))
    fresh_c = fresh_conn.cursor()
    fresh_c.execute("SELECT jobs FROM people WHERE id = ?", (rec['id'],))
    fresh_row = fresh_c.fetchone()
    fresh_conn.close()
    
    if fresh_row and fresh_row[0]:
        fresh_jobs = json.loads(fresh_row[0])
        st.success(f"✅ Companies and positions updated! Jobs: {', '.join(fresh_jobs)}")
```

## Example Flow

User selects positions for companies:
- **ikea**: Sales, Stock
- **free_coffee**: Barista
- **decima**: Security, IT

→ `update_person()` is called with `companies` parameter

→ Jobs are derived: ["Barista", "IT", "Sales", "Security", "Stock"] (sorted, deduplicated)

→ SQL UPDATE executes with both companies JSON and jobs JSON

→ `conn.commit()` writes to disk

→ Direct DB query confirms save

→ Success message shows derived jobs

## Key Points

1. **conn.commit()** is ALWAYS called in update_person() - changes are persisted
2. **Jobs are derived automatically** from companies when companies parameter is provided
3. **Direct DB query** after save bypasses any caching issues
4. **JSON serialization** ensures proper storage: `json.dumps(data, ensure_ascii=False)`

## Testing Commits

You can verify commits are working by running:

```bash
python3 << 'EOF'
import sys, sqlite3, json
sys.path.insert(0, 'src')
from catprint import utils

# Update a person
utils.update_person("150", companies={"ikea": ["Sales"], "free_coffee": ["Barista"]})

# Query directly from DB
conn = sqlite3.connect('src/data/people.db')
c = conn.cursor()
c.execute("SELECT jobs, companies FROM people WHERE id = ?", ("150",))
row = c.fetchone()
conn.close()

print(f"Jobs in DB: {json.loads(row[0])}")
print(f"Companies in DB: {json.loads(row[1])}")
EOF
```
