FATORI-V • FI Profiles
======================

This folder holds AREA and TIME profiles for the fault injection engine.

Profiles are responsible for:
  - AREA: deciding *where* to inject (which targets or addresses).
  - TIME: deciding *when* to inject (schedule, rate, duration).

Each profile is implemented as a Python module under:

  fi/profiles/area/<name>.py
  fi/profiles/time/<name>.py

and must export a small, uniform "plugin" API:

  PROFILE_NAME   (optional, string)
  PROFILE_KIND   (optional, "area" or "time")

  def describe() -> str
    Short human description of what the profile does.

  def default_args() -> dict[str, object]
    Dictionary of default parameters for the profile. This is used
    for documentation and as a base for argument parsing.

  def make_profile(
      args: dict[str, object],
      *,
      global_seed: int | None,
      settings,
  ) -> object:
    Factory that instantiates the profile object. The returned object
    is usually a subclass of AreaProfileBase or TimeProfileBase.

The engine loads profiles dynamically by module name and calls
make_profile(...) with a dictionary of parsed arguments and the
global seed taken from the Config object.

---

## Related Documentation

### Core Systems
- [Main README](../Readme.md) - System overview, profile sections
- [Config System](../core/config/Readme.md) - Profile configuration and seeds
- [Campaign Controller](../core/campaign/Readme.md) - Profile execution

### Profiles
- [Area Profiles](area/Readme) - WHERE to inject (target selection)
- [Time Profiles](time/Readme) - WHEN to inject (campaign scheduling)

### Targets
- [Target System](../targets/Readme.md) - TargetPool built by area profiles

### Backends
- [Backend Overview](../backend/Readme.md) - Used by profiles indirectly
- [ACME Backend](../backend/acme/Readme.md) - Address expansion for area profiles

### See Also
- `fi_settings.py` - Profile default arguments
- Profile loading system (common/loader.py in area/ and time/)
- Creating custom profiles (see area/Readme and time/Readme)
