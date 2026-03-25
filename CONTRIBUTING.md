# Contributing

### Tools Used

- **Python 3.9 / 3.12** — developed locally on macOS, tested on Nuvolos
- **Selenium** — chosen over Scrapy because Waitrose renders product data via JavaScript/React (see `scraper/README.md` for justification)
- **VS Code** — primary editor
- **Git / GitHub** — version control with feature branches following GitFlow conventions
- **Chrome DevTools** — used to inspect Waitrose page structure and identify `__NEXT_DATA__` as the data source

### AI Assistance

Claude (Anthropic) was used as a development assistant throughout the project for:

- Debugging Selenium selectors and anti-bot detection issues
- Designing the recursive subcategory drilling approach
- Structuring the FastAPI endpoints and Pydantic models
- Writing and refining documentation

All code was reviewed and understood before committing. AI suggestions were adapted to fit the project's specific requirements rather than used verbatim.

### Course Materials Referenced

- **W01 Lab** — Open Food Facts API and NOVA classification system
- **W02-W03 Lectures** — Scrapy vs Selenium decision, web scraping ethics, `robots.txt` compliance
- **W05 Lecture** — FastAPI structure, Pydantic v2 models with `Field(description=...)`, pre-enrichment pattern

### Collaboration Model

This project follows the assignment's handoff model:

- **Part A (Scraper):** Built on the `main` branch
- **Part B (API):** Built on the `feature/api` branch of the assigned partner's repository
- **Improvements:** Addressed on `feature/scraper-improvements` following formative feedback
