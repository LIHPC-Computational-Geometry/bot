class Observable:
    """Classe de base pour doter les modèle de capacités de notification."""

    def __init__(self) -> None:
        self._observers = []

    def add_observer(self, observer) -> None:
        self._observers.append(observer)

    def remove_observer(self, observer) -> None:
        self._observers.remove(observer)

    def _notify_observers(self) -> None:
        for observer in self._observers:
            observer.update(self)
