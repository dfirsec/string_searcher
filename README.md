# String Searcher

This script allows you to search all text-based files in a directory for a given string.

## Features

Supports both simple string matching and regular expressions

Recursive search with a specified depth level

Customizable file extensions to search

## Installation

1. Clone the repository or download the script files.

```text
git clone https://github.com/dfirsec/string_searcher.git
```

2. Navigate to the project directory:

```text
cd string_searcher
```

3. Install the dependencies using poetry:

```text
pip install poetry

poetry install
```

## Usage

1. Create the virtual environment

```text
poetry shell
```

2. Run using the following commands:

```text
python string_searcher.py <directory> <search_term> [--depth <depth>] [-e <extensions>]
```

**`<directory>`**: The directory to search in.

**`<search_term>`**: The string to search for.

**`--depth <depth>`**: The maximum depth to recurse into subdirectories. Default is 1. Use '--depth -1' for all subdirectories.

**`-e <extensions>`**: The file extensions to search within. Provide a comma-separated list. Default extensions include **`.txt`, `.md`, `.csv`, `.xml`, `.html`, `.py`, `.js`, `.css`, `.yml`, `.yaml`**.

## Dependencies

**`rich`**: For rich console output.

## License

This script is licensed under the MIT License. Feel free to modify and use it according to your needs.

## Credits

The script utilizes the rich library for enhanced console output.

The banner text used in the script is courtesy of [Manytools](https://manytools.org/hacker-tools/ascii-banner/).