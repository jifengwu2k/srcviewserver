# `srcviewserver`

A simple HTTP server that serves source files with syntax highlighting.  

Source files with a recognized language extension are highlighted and wrapped in an HTML page.  
All other files are served as-is (binary streaming). Directories get an HTML listing.

## Installation

```
pip install srcviewserver
```

## Usage

```
srcviewserver [--port PORT] [--bind ADDRESS]
```

| Option       | Default       | Description               |
|------------- |-------------- |-------------------------- |
| `--bind -b`  | `127.0.0.1`   | Address to bind to.       |
| `--port -p`  | `8000`        | Port to listen on.        |

Navigate to `http://127.0.0.1:8000/` and browse the directory tree.

## Contributing

Contributions are welcome! Please submit pull requests or open issues on the GitHub repository.

## License

This project is licensed under the [MIT License](LICENSE).
