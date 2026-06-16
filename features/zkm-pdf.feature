# zkm-pdf key journeys — manual checklist.
# The plugin has no own CLI/UI; its user-facing surface is `zkm convert pdf`
# through core, which cannot be browser-automated. Run against a scratch store
# (ZKM_STORE=/tmp/kb zkm init) with this repo discovered under plugins/zkm-pdf.

@manual
Feature: Import text PDFs into the knowledge store

  Background:
    Given a freshly initialized scratch store
    And zkm-config.yaml configures the pdf plugin with source_dir pointing at a folder of test PDFs

  @manual
  Scenario: Born-digital PDF becomes a searchable markdown note
    Given the source folder contains a text PDF with /Title, /Author and /CreationDate metadata
    When I run "zkm convert pdf"
    Then a file pdfs/YYYY/MM/<creation-date>_<slug>.md exists with that date in its path
    And its frontmatter carries source, sha256, original, pages, title and author
    And running "zkm index" followed by "zkm search <phrase from the PDF body>" finds the new note

  @manual
  Scenario: Scanned-only PDF is left for zkm-scan
    Given the source folder contains a scanned PDF with no text layer
    When I run "zkm convert pdf"
    Then no markdown file is created for it
    And <store>/.zkm-state/zkm-pdf-skipped.jsonl gains one entry naming the file
    And the command exits 0 without error output

  @manual
  Scenario: Mail attachment PDF is imported without duplicating bytes
    Given zkm-eml has previously deposited a PDF attachment into inbox/ via CAS symlink
    When I run "zkm convert pdf" with no source_dir configured
    Then a pdfs/YYYY/MM/*.md note is created whose frontmatter original points at originals/mail/_objects/...
    And the CAS sidecar lists both an "eml" and a "pdf" producer
    And no second copy of the PDF bytes exists under originals/pdfs/

  @manual
  Scenario: Re-running the convert is a no-op
    Given a previous "zkm convert pdf" run imported all PDFs
    When I run "zkm convert pdf" again
    Then it reports zero new files and creates no new git commit

  @manual
  Scenario: Empty-user-password PDF is decrypted transparently (id:58d7)
    Given the source folder contains a copy-restricted PDF protected with an empty user password
    When I run "zkm convert pdf"
    Then a pdfs/YYYY/MM/*.md note is created for it as for any born-digital PDF
    And no entry is written to <store>/.zkm-state/zkm-pdf-skipped.jsonl for that file

  @manual
  Scenario: Non-empty-password PDF queues as encrypted-pending, no artifacts (id:1a30)
    Given the source folder contains a PDF protected with a non-empty user password I do not supply
    When I run "zkm convert pdf"
    Then no markdown file, CAS object, or inbox symlink is created for it
    And <store>/.zkm-state/zkm-pdf-skipped.jsonl gains one entry with reason "encrypted-pending"
    And the command exits 0 and sibling valid PDFs in the same run are still imported

  @manual
  Scenario: Encrypted-pending PDF self-drains from its originating mail (id:1a30)
    Given a prior run queued an inbox PDF as encrypted-pending
    And zkm-eml later imports the mail that carried that PDF, whose body says "PDF password: hunter2"
    When I run "zkm convert pdf" again
    Then the previously-pending PDF is decrypted with that password and imported normally
    And its encrypted-pending entry is not re-logged on subsequent runs
