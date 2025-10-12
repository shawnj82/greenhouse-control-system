# 💰 Shared Relay Control System

## 🎯 **Cost-Effective Light Control**

The shared relay system allows multiple lights to be controlled by a single relay, reducing hardware costs while maintaining effective grow light management.

## 💡 **When to Use Shared Relays**

### ✅ **Ideal Scenarios:**
- **Same Growing Zone**: Lights serving the same crop area
- **Backup/Redundant Lights**: Multiple lights providing supplemental coverage
- **Seed Starting Areas**: Small area lights that work together
- **Budget Constraints**: Cost-sensitive installations
- **Limited GPIO Pins**: When Raspberry Pi pins are scarce

### ❌ **Avoid Shared Relays When:**
- **Different Growth Stages**: Seedlings vs flowering plants needing different schedules
- **Different Light Types**: Mixing incompatible spectrums (blue vs red dominant)
- **Independent Control Needed**: Lights requiring separate on/off timing
- **High Power Mismatch**: Vastly different power requirements

## 🔧 **Configuration**

### **File Structure**
```
data/
├── lights.json          # Individual light definitions
└── relay_groups.json    # Shared relay group configuration
```

### **Example Configuration (`relay_groups.json`)**
```json
{
  "relay_groups": {
    "greenhouse_east_upper": {
      "description": "East side upper shelf grow lights",
      "relay_pin": 23,
      "active_high": true,
      "lights": ["led_strip_1", "grow_panel_1"],
      "cost_reasoning": "Both serve same growing area",
      "power_total_watts": 145
    },
    "seed_starting_area": {
      "description": "Seed starting table lights", 
      "relay_pin": 24,
      "active_high": true,
      "lights": ["basic_light_1", "rgb_light_1"],
      "cost_reasoning": "Seedlings need consistent light",
      "power_total_watts": 85
    }
  }
}
```

### **Individual Light Configuration (`lights.json`)**
```json
{
  "lights": {
    "led_strip_1": {
      "name": "Full Spectrum LED Strip 1",
      "power_watts": 45,
      "zone_key": "A1"
      // Note: No relay_pin - controlled by group
    },
    "individual_light": {
      "name": "Independent Light",
      "relay_pin": 22,  // Individual control
      "power_watts": 30,
      "zone_key": "B1"
    }
  }
}
```

## 🚀 **Quick Setup**

### **1. Interactive Configuration Tool**
```bash
python configure_shared_relays.py
```

**Features:**
- View current configuration
- Get automatic grouping suggestions
- Create new relay groups
- Test group functionality
- Generate efficiency reports

### **2. Manual Configuration**
1. **Edit `relay_groups.json`** with your desired groups
2. **Remove `relay_pin`** from individual lights that join groups
3. **Test configuration** with the tool

### **3. Hardware Wiring**
```
Relay Module → Raspberry Pi
VCC         → 5V (Pin 2)
GND         → Ground (Pin 6)
IN1         → GPIO 23 (group 1)
IN2         → GPIO 24 (group 2)

Light Group Wiring:
AC Power → Relay NC/NO → All Lights in Group (parallel)
```

## 🧠 **How It Works**

### **Individual Light Control**
```python
# Request: Turn on light_1
controller.turn_on_light("light_1")

# If light_1 is in a group with light_2:
# Result: Both light_1 AND light_2 turn on
```

### **Group Decision Logic**
- **ANY light in group wants ON** → Entire group turns ON
- **ALL lights in group want OFF** → Entire group turns OFF
- **Mixed requests** → Group stays ON (safety bias)

### **Example Scenario**
```python
# Group: ["seedling_light_1", "seedling_light_2"]
controller.turn_on_light("seedling_light_1")   # Both lights ON
controller.turn_off_light("seedling_light_1")  # Both lights still ON (light_2 not explicitly off)
controller.turn_off_light("seedling_light_2")  # Now both lights OFF
```

## 📊 **Cost Analysis**

### **Traditional Setup (Individual Relays)**
```
5 lights × 1 relay each = 5 relays
5 relays × $3 each = $15
5 GPIO pins used
```

### **Optimized Setup (Shared Relays)**
```
Group 1: 3 lights → 1 relay
Group 2: 2 lights → 1 relay
Total: 5 lights × 2 relays = $6
3 GPIO pins saved, $9 saved (60% cost reduction)
```

### **Real-World Example**
| Scenario | Individual Cost | Shared Cost | Savings |
|----------|----------------|-------------|---------|
| Small greenhouse (8 lights) | $24 | $9 | $15 (62%) |
| Seed starting (4 lights) | $12 | $3 | $9 (75%) |
| Large setup (20 lights) | $60 | $18 | $42 (70%) |

## 🛠️ **Advanced Features**

### **Automatic Optimization**
```python
# Get grouping suggestions
controller = EnhancedLightController(lights_config)
suggestions = controller.optimize_relay_grouping()

# Apply suggestions automatically
controller.apply_optimization_suggestions(suggestions, auto_assign_pins=True)
```

### **Dynamic Group Management**
```python
# Create group at runtime
controller.create_light_group(
    group_id="new_group",
    light_ids=["light_a", "light_b"],
    relay_pin=25,
    description="Dynamic group"
)

# Remove group (converts back to individual control)
controller.remove_light_group("new_group")
```

### **Efficiency Reporting**
```python
report = controller.get_relay_usage_report()
print(f"Total relays saved: {report['relays_saved']}")
print(f"Cost savings: {report['cost_savings_percent']:.1f}%")
```

## ⚡ **Power Considerations**

### **Relay Capacity**
- **Typical 5V relay**: 10A @ 250VAC / 10A @ 30VDC
- **LED grow lights**: Usually 0.5-3A each
- **Safety margin**: Stay under 80% of relay rating

### **Power Calculation**
```python
# Example: 3 lights @ 45W each on 120VAC
total_watts = 3 × 45 = 135W
current = 135W ÷ 120V = 1.125A
relay_capacity = 10A
safety_factor = 0.8
max_safe_current = 10A × 0.8 = 8A
# Result: Safe ✅ (1.125A < 8A)
```

### **Fuse Protection**
- Add appropriate fuses for each group
- **Recommended**: 5A fuse for groups under 500W
- **Wire gauge**: 14 AWG for up to 15A loads

## 🔍 **Troubleshooting**

### **Lights Not Responding**
1. **Check wiring**: Verify relay connections
2. **Test individual relay**: Use multimeter to confirm switching
3. **Power supply**: Ensure adequate current capacity
4. **Configuration**: Verify `relay_groups.json` syntax

### **Partial Group Control**
1. **Wiring issue**: Check parallel connections to all lights
2. **Burned out bulb**: One light may have failed
3. **Different power requirements**: Incompatible lights in group

### **GPIO Conflicts**
1. **Pin collision**: Check for duplicate pin assignments
2. **Reserved pins**: Avoid pins used by I2C, SPI, UART
3. **Hardware limitations**: Some pins have special functions

## 📋 **Best Practices**

### **Grouping Strategy**
1. **Same zone/crop**: Group lights serving identical purposes
2. **Similar power**: Keep power differences under 50%
3. **Growth stage**: Match lighting schedules and requirements
4. **Physical proximity**: Easier wiring and troubleshooting

### **Safety Guidelines**
1. **Electrical isolation**: Use appropriate relays for AC loads
2. **Proper grounding**: Ensure all equipment is grounded
3. **Circuit protection**: Fuses or breakers for each group
4. **Wire management**: Strain relief and proper gauge wiring

### **Documentation**
1. **Label groups**: Clear descriptions of purpose
2. **Track changes**: Note modifications to groups
3. **Power calculations**: Document total wattage per group
4. **Wiring diagrams**: Keep schematic of connections

## 🧪 **Testing Your Setup**

### **Basic Functionality Test**
```bash
python configure_shared_relays.py
# Select option 4: Test relay groups
```

### **Manual Testing**
```python
from control.enhanced_relay import EnhancedLightController
controller = EnhancedLightController(lights_config, relay_groups_config)

# Test group behavior
controller.turn_on_light("group_light_1")
states = controller.get_all_light_states()
print("All group lights should be ON:", states)

controller.cleanup()
```

### **Integration Testing**
```python
# Test with main system
from control.light_calibration import LightCalibrator
calibrator = LightCalibrator()

# Run intelligent control with shared relays
decisions = calibrator.make_intelligent_light_decisions()
calibrator.apply_intelligent_decisions(decisions)
```

## 💡 **Tips for Success**

### **Start Small**
- Begin with 2-3 lights in obvious groups
- Test thoroughly before expanding
- Monitor power consumption and performance

### **Plan for Growth**
- Reserve GPIO pins for future expansion
- Document your grouping strategy
- Consider seasonal lighting changes

### **Monitor Performance**
- Use the efficiency reporting tools
- Track cost savings over time
- Adjust groups based on actual usage patterns

---

> **💰 Bottom Line**: Shared relay control can reduce hardware costs by 60-75% while maintaining effective grow light management. Perfect for budget-conscious growers who need multiple lights in defined zones!
