import { Ionicons } from '@expo/vector-icons';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { useAuth } from '../context/AuthContext';
import AdminScreen from '../screens/AdminScreen';
import HomeScreen from '../screens/HomeScreen';
import LoginScreen from '../screens/LoginScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import VehicleScreen from '../screens/VehicleScreen';
import ZonesScreen from '../screens/ZonesScreen';
import { colors } from '../theme';
import { esAdmin } from '../types';

const Tab = createBottomTabNavigator();

type IconName = React.ComponentProps<typeof Ionicons>['name'];
const icon = (name: IconName) => ({ color, size }: { color: string; size: number }) => <Ionicons name={name} color={color} size={size} />;

export default function Navigation() {
  const { usuario, cargando } = useAuth();
  if (cargando) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primary }}>
        <ActivityIndicator color="#fff" size="large" />
      </View>
    );
  }
  if (!usuario) return <LoginScreen />;

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.primary },
          headerTintColor: '#fff',
          tabBarActiveTintColor: colors.primary,
        }}
      >
        <Tab.Screen name="Inicio" component={HomeScreen} options={{ tabBarIcon: icon('speedometer-outline') }} />
        <Tab.Screen name="Islas" component={ZonesScreen} options={{ tabBarIcon: icon('grid-outline') }} />
        <Tab.Screen name="Avisos" component={NotificationsScreen} options={{ tabBarIcon: icon('notifications-outline') }} />
        <Tab.Screen name="Mi cuenta" component={VehicleScreen} options={{ tabBarIcon: icon('car-outline') }} />
        {esAdmin(usuario) ? <Tab.Screen name="Admin" component={AdminScreen} options={{ tabBarIcon: icon('shield-checkmark-outline') }} /> : null}
      </Tab.Navigator>
    </NavigationContainer>
  );
}
