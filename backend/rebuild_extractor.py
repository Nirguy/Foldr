"""Rebuild extractor.py by replacing the visual assets section with the original from commit a9ce70c."""

with open("app/extractor.py", "r") as f:
    current = f.readlines()

with open("extractor_original.py", "r") as f:
    original = f.readlines()

# Current file: extract_visual_assets starts at line 688 (0-indexed: 687)
# Current file: run_extraction starts at line 1570 (0-indexed: 1569)
# Original file: extract_visual_assets starts at line 519 (0-indexed: 518)
# Original file: run_extraction starts at line 1401 (0-indexed: 1400)

# Keep everything before extract_visual_assets from current
before = current[:687]

# Take extract_visual_assets + all helpers from original (lines 519-1400)
middle = original[518:1400]

# Keep run_extraction onwards from current
after = current[1569:]

result = before + middle + after

with open("app/extractor.py", "w") as f:
    f.writelines(result)

print(f"Before: {len(before)} lines")
print(f"Middle (from original): {len(middle)} lines")
print(f"After: {len(after)} lines")
print(f"Total: {len(result)} lines")
