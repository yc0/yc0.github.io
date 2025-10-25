#!/usr/bin/env python3
import os
import re
from pathlib import Path
import yaml
from datetime import datetime

def parse_hexo_frontmatter(file_path):
    """Parse Hexo YAML frontmatter from Markdown file"""
    content = Path(file_path).read_text(encoding='utf-8')
    
    # Find frontmatter between --- markers
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    
    if not frontmatter_match:
        print(f"No frontmatter found in {file_path.name}")
        return None, content
    
    frontmatter_str = frontmatter_match.group(1)
    try:
        metadata = yaml.safe_load(frontmatter_str) or {}
        body = content[frontmatter_match.end():]
        return metadata, body
    except yaml.YAMLError as e:
        print(f"YAML error in {file_path.name}: {e}")
        return None, content

def convert_to_hugo_frontmatter(hexo_meta):
    """Convert Hexo metadata to Hugo format"""
    hugo_meta = {}
    
    # Direct mappings
    mapping = {
        'title': 'title',
        'date': 'date',
        'updated': 'lastmod',
        'tags': 'tags',
        'category': 'categories',
        'subtitle': 'subtitle',
    }
    
    for hexo_key, hugo_key in mapping.items():
        if hexo_key in hexo_meta:
            hugo_meta[hugo_key] = hexo_meta[hexo_key]
    
    # Convert string tags to list
    if 'tags' in hugo_meta:
        if isinstance(hugo_meta['tags'], str):
            hugo_meta['tags'] = [tag.strip() for tag in hugo_meta['tags'].split(',')]
        elif not isinstance(hugo_meta['tags'], list):
            hugo_meta['tags'] = [str(hugo_meta['tags'])]
    
    # Convert single category to list
    if 'categories' in hugo_meta and not isinstance(hugo_meta['categories'], list):
        hugo_meta['categories'] = [hugo_meta['categories']]
    
    # Add Hugo defaults
    hugo_meta.setdefault('draft', False)
    
    # Ensure date is in ISO format if present
    if 'date' in hugo_meta and isinstance(hugo_meta['date'], str):
        try:
            date_obj = datetime.strptime(hugo_meta['date'], '%Y-%m-%d %H:%M:%S')
            hugo_meta['date'] = date_obj.isoformat()
        except ValueError:
            pass  # Keep original if can't parse
    
    return hugo_meta

def write_hugo_post(file_path, hugo_meta, body):
    """Write post with Hugo frontmatter"""
    frontmatter_yaml = yaml.dump(hugo_meta, default_flow_style=False, allow_unicode=True)
    new_content = f"---\n{frontmatter_yaml}---\n\n{body}"
    
    Path(file_path).write_text(new_content, encoding='utf-8')

def main():
    posts_dir = Path("../content/posts")
    
    if not posts_dir.exists():
        print(f"Error: {posts_dir} not found. Make sure you're in Hugo root.")
        return
    
    converted = 0
    skipped = 0
    
    for post_path in posts_dir.glob("*.md"):
        try:
            hexo_meta, body = parse_hexo_frontmatter(post_path)
            
            if hexo_meta is None:
                print(f"⚠️  Skipped {post_path.name} (no frontmatter)")
                skipped += 1
                continue
            
            hugo_meta = convert_to_hugo_frontmatter(hexo_meta)
            
            # Add original filename as slug if needed
            if 'slug' not in hugo_meta:
                hugo_meta['slug'] = post_path.stem
            
            write_hugo_post(post_path, hugo_meta, body)
            print(f"✓ Converted {post_path.name}")
            converted += 1
            
        except Exception as e:
            print(f"✗ Error processing {post_path.name}: {e}")
            skipped += 1
    
    print(f"\n✅ Migration complete: {converted} converted, {skipped} skipped")

if __name__ == "__main__":
    main()