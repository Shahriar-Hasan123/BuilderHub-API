# Publish Versioning Report

## Overview

The publish versioning system creates an immutable snapshot of a site's publishable content. Each publish converts the current site and page source into JSON assets, stores their content by SHA-256 hash, writes the published files to media storage, and records a `SitePublishVersion` database row.

Rollback restores editable source from a selected historical version and republishes the restored state. The original historical version is preserved; hash-based deduplication determines whether the restored state reuses an existing version or creates a new one.

## Main Components

- `PublishService`: validates, builds, publishes, and compares published versions.
- `RollbackService`: coordinates rollback confirmation, restoration, and republishing.
- `RestoreService`: restores site and page source from a selected version.
- `PublishContentService`: validates source readiness, minifies HTML, and builds JSON.
- `PublishAssetService`: manages published files, CSS snapshots, cleanup, and public URLs.
- `PublishVersionService`: calculates hashes and creates or reuses version records.
- `HTMLMinifier`: normalizes and minifies header, footer, and page HTML.
- `HTMLToJSONConverter`: converts editable site and page data into JSON structures.
- `BlobStore`: stores immutable text and CSS content using SHA-256 content hashes.
- `SitePublishVersion`: records version number, JSON hashes, CSS asset hashes, and publisher information.
- `Site.current_published_version`: points to the active published version.

## What Is Versioned

### JSON content

The following generated JSON content is hashed and stored in the blob store:

- Site header JSON
- Site footer JSON
- One JSON file per publishable page

### Editable CSS assets

The following editable CSS files are stored as binary blobs and recorded in `asset_hashes`:

- Site global CSS
- Page CSS

### Image references

Images are treated as immutable uploaded assets. Their file contents are not copied into the version blob store. Published JSON stores their paths, and rollback restores those paths:

- Site favicon
- Site logo
- Site thumbnail
- Page hero image

This avoids duplicating image bytes while preserving the published reference.

## Publish Workflow

1. Select enabled pages with non-empty HTML.
2. Validate that the site has non-empty header and footer files and at least one publishable page.
3. Minify the header, footer, and page HTML.
4. Convert the content into JSON.
5. Serialize JSON with two-space indentation and a trailing newline.
6. Store JSON content in `BlobStore` and receive SHA-256 hashes.
7. Snapshot editable CSS files and receive their content hashes.
8. Write `header.json`, `footer.json`, and page JSON files to `published/sites/{site-slug}/`.
9. Remove orphaned page JSON files that are not part of the current publish.
10. Lock the site database row with `select_for_update()`.
11. Reuse an existing version when all JSON and CSS hashes match; otherwise create a new version number. Rollback uses the same hash-based deduplication rule.
12. Mark the site and selected pages as published.
13. Update `current_published_version`.

## Version Deduplication

A new version is not created when the following values all match an existing version:

- Header hash
- Footer hash
- Page hash mapping
- Editable asset hash mapping

Therefore, republishing unchanged content reuses the existing version instead of creating duplicate history entries.

## Unpublished Change Detection

`has_unpublished_changes()` rebuilds the current JSON content and CSS asset hash mapping, then compares them with the active version.

It returns `True` when any of these change:

- Header content
- Footer content
- Page content or page set
- Site global CSS
- Page CSS

This check is used before rollback. If unpublished changes exist, the API returns a warning and requires explicit confirmation before overwriting them.

## Rollback Workflow

1. Verify that the selected version belongs to the requested site.
2. Check for unpublished changes.
3. Require `?confirm=true` when rollback would discard draft changes.
4. Read header, footer, and page JSON blobs from `BlobStore`.
5. Restore site name, header HTML, footer HTML, and global CSS.
6. Restore site image references from the historical JSON paths.
7. Restore pages from the selected version, creating missing pages when necessary.
8. Restore page titles, metadata, page type, HTML, CSS, and hero-image references.
9. Delete database pages that do not exist in the selected historical version.
10. Republish the restored source.
11. Create or reuse a publish version for the restored state using the normal hash-based deduplication rule.
12. Return the source version, target version, restored pages, and removed pages.

## Rollback Example

Initial state:

```text
Version 1: home, about
```

After editing:

```text
Version 2: home, service
```

When rolling back to Version 1:

```text
- home is restored from Version 1
- about is recreated or restored from Version 1
- service is deleted from the database because it is absent from Version 1
- header, footer, page HTML, and CSS are restored
- image paths are restored from the Version 1 JSON snapshot
- the restored state is published again and is deduplicated by its hashes
```

The original Version 1 remains unchanged. If the restored content already matches
an existing version, that version is reused; otherwise a new version is created.

## Workflow Diagrams

### Publish Flow

```text
Publish request
    |
    v
Select enabled pages with non-empty HTML
    |
    v
Validate site header, footer, and page readiness
    |
    v
Minify header, footer, and page HTML
    |
    v
Convert site and page content into JSON
    |
    +-- header.json
    +-- footer.json
    +-- pages/{slug}.json
    |
    v
Hash generated JSON content
    |
    v
Hash editable CSS files
    |
    v
Write JSON files to published storage
    |
    v
Lock Site database row
    |
    v
Compare current hashes with existing versions
    |
    |-- all hashes match -> reuse existing version
    |
    |-- hashes differ    -> create new SitePublishVersion
    |
    v
Mark Site and selected Pages as published
    |
    v
Set Site.current_published_version
    |
    v
Publish complete
```

### Version Comparison Flow

```text
Current editable Site and Pages
    |
    v
Generate current JSON and CSS hash values
    |
    v
Compare with current published version
    |
    +-- header hash changed?  -> unpublished changes
    +-- footer hash changed?  -> unpublished changes
    +-- page hashes changed? -> unpublished changes
    +-- CSS hashes changed?  -> unpublished changes
    |
    +-- no differences -> no unpublished changes
```

### Rollback Flow

```text
Rollback request for Version N
    |
    v
Load Version N for the requested Site
    |
    v
Check for unpublished changes
    |
    |-- changes exist and confirm=true is missing
    |       |
    |       v
    |   Return HTTP 409 warning
    |
    |-- no changes or confirm=true
        |
        v
    Read JSON and CSS blobs for Version N
        |
        v
    Restore Site name, header, footer, and global CSS
        |
        v
    Restore image path references
        |
        v
    Restore Pages, HTML, metadata, CSS, and hero-image paths
        |
        v
    Delete database Pages absent from Version N
        |
        v
    Republish the restored editable state
        |
        v
    Create or reuse the rollback result version
        |
        v
    Rollback complete
```

The rollback flow does not modify the original historical version. It restores
that version's source and publishes the result as the latest active version.
If the restored hashes match an existing version, that version is reused.

## Public Rendering

The published JSON files are rendered by `PublishedPageView` through the Django
template `templates/published_site.html`. Public routes are separate from the
API routes:

```text
GET /published/{site-slug}/
GET /published/{site-slug}/{page-slug}/
```

The view reads the published header, page, and footer JSON files and passes the
complete objects to the template. The template renders the published HTML,
metadata, favicon, and CSS references. It does not read draft site or page
content directly from the database.

## Consistency and Transaction Notes

Database status changes, version creation, and page status updates occur inside `transaction.atomic()`. The site row is locked while allocating a new version number.

Published files are stored separately from the database. Database transactions cannot roll back storage writes, so the file replacement helper preserves the previous published file when a write fails. The blob store keeps immutable content available for later rollback.

## Result

The system provides:

- Immutable publish history
- Content-based version deduplication
- Readable published JSON files
- Detection of unpublished changes
- Explicit protection against accidental draft loss
- Restoration of editable HTML, CSS, page records, and image references
- A new version created only when a rollback produces content not already represented by an existing version
