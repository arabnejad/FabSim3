from rich.console import Console

# https://docs.python.org/3/library/exceptions.html#exception-hierarchy

class FabSimError:
    # Initialize the console object as a class attribute
    console = Console()

    @staticmethod
    def RuntimeError(message, details=None):
        FabSimError.console.print(f"[red]RuntimeError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [white]{details}[/white]")
        raise RuntimeError(message, details)

    @staticmethod
    def TypeError(message, details=None):
        FabSimError.console.print(f"[red]TypeError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise TypeError(message, details)

    @staticmethod
    def ValueError(message, details=None):
        FabSimError.console.print(f"[red]ValueError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise ValueError(message, details)

    @staticmethod
    def FileNotFoundError(message, details=None):
        FabSimError.console.print(f"[red]FileNotFoundError:[/red]  [white]{message}[/white]")

        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise FileNotFoundError(message, details)

    @staticmethod
    def AttributeError(message, details=None):
        FabSimError.console.print(f"[yellow]AttributeError:[/yellow]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[yellow]Details:[/yellow] [bold]{details}[/bold]")
        raise AttributeError(message, details)

    @staticmethod
    def NotImplementedError(message, details=None):
        FabSimError.console.print(f"[red]NotImplementedError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise NotImplementedError(message, details)

    @staticmethod
    def ImportError(message, details=None):
        FabSimError.console.print(f"[red]ImportError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise ImportError(message, details)

    @staticmethod
    def KeyError(message, details=None):
        FabSimError.console.print(f"[red]KeyError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise KeyError(message, details)

    @staticmethod
    def UnboundLocalError(message, details=None):
        FabSimError.console.print(f"[red]UnboundLocalError:[/red]  [white]{message}[/white]")
        if details:
            FabSimError.console.print(f"[red]Details:[/red] [bold]{details}[/bold]")
        raise UnboundLocalError(message, details)
