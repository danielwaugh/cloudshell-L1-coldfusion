# coldfusion L1 Driver

## Overview
The coldfusion L1 Driver provides CloudShell Resource Manager with the capability to communicate with switches that are part of the CloudShell inventory.

End users will be able to create routes, configure port settings, and read values from the switch using the CloudShell Portal, Resource Manager client, or the CloudShell API.

### Requirements
The driver is compatible with the following CloudShell versions:
- 7.0 and above

### Supported Devices/Firmwares
The driver has been verified with the following devices and software versions:
- Device_Type - Version/s

### Installation

1. Extract ColdFusion_L1_Driver.zip to C:\Program Files (x86)\QualiSystems\CloudShell\Server\Drivers

2. Import new Data-Model from C:\Program Files (x86)\QualiSystems\CloudShell\Server\Drivers\cloudshell-L1-
coldfusion\datamodel\virtual_wire_ResourceConfiguration.xml to the CloudShell

3. Create new resource according to the new Data-Model, Create Resource Steps

4. Do auto-load for the new resource

### Supported Functionality

| Feature | Description |
| ------ | ------ |
| AutoLoad | Creates the sub-resources of the L1 switch |
| MapBidi | Creates a bi-directional connection between two ports |
| MapUni | Creates a uni-directional connection between two ports |
| MapClear | Clears any connection ending in this port |
| MapClearTo | Clears a uni-directional connection between two ports |

### Known Issues
